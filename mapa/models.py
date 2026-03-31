from django.db import models


class Servico(models.Model):
    """Serviço extraído dos relatórios do sistema Flip."""

    numero_os = models.CharField(max_length=100, blank=True, verbose_name="Número OS")
    tipo_servico = models.CharField(max_length=200, verbose_name="Tipo de Serviço")
    status = models.CharField(max_length=100, verbose_name="Status")

    endereco = models.CharField(max_length=500, verbose_name="Endereço")
    endereco_normalizado = models.CharField(max_length=500, blank=True,
                                            verbose_name="Endereço (busca)")
    bairro = models.CharField(max_length=200, blank=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=200, blank=True, verbose_name="Cidade")
    cep = models.CharField(max_length=20, blank=True, verbose_name="CEP")

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    data_abertura = models.DateField(null=True, blank=True, verbose_name="Data Abertura")
    data_execucao = models.DateField(null=True, blank=True, verbose_name="Data Execução")
    data_conclusao = models.DateField(null=True, blank=True, verbose_name="Data Conclusão")
    data_finalizacao = models.DateField(null=True, blank=True, verbose_name="Data Finalização")

    fiscal = models.CharField(max_length=200, blank=True, verbose_name="Fiscal / Responsável")

    criado_em = models.DateTimeField(auto_now_add=True)
    fonte = models.CharField(max_length=50, default='relatorio', verbose_name="Fonte")

    class Meta:
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"
        ordering = ['-data_abertura']

    def __str__(self):
        return f"{self.tipo_servico} - {self.endereco}"

    @property
    def geocodificado(self):
        return self.latitude is not None and self.longitude is not None


class ConsultaProgramada(models.Model):
    """Consultas em aberto com endereço e data programada (controle interno)."""

    endereco = models.CharField(max_length=500, verbose_name="Endereço")
    bairro = models.CharField(max_length=200, blank=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=200, blank=True, verbose_name="Cidade")

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    tipo_servico = models.CharField(max_length=200, verbose_name="Tipo de Serviço")
    data_programada = models.DateField(verbose_name="Data Programada")
    observacao = models.TextField(blank=True, verbose_name="Observação")

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Consulta Programada"
        verbose_name_plural = "Consultas Programadas"
        ordering = ['data_programada']

    def __str__(self):
        return f"{self.tipo_servico} - {self.endereco} ({self.data_programada})"

    @property
    def geocodificado(self):
        return self.latitude is not None and self.longitude is not None


TIPOS_SERVICO_PROG = {
    '01': 'Lavagem Especial',
    '02': 'Limpeza de Monumentos',
    '09': 'Boca de Lobo',
    '11': 'Mutirão de Zeladoria',
    '12': 'Cata-Bagulho',
    '13': 'Núcleos Habitacionais',
}


class ProgramacaoServico(models.Model):
    """Plano de trabalho importado da pasta Programação (por subprefeitura e tipo)."""

    subprefeitura   = models.CharField(max_length=100, verbose_name="Subprefeitura")
    tipo_nome       = models.CharField(max_length=100, verbose_name="Tipo de Serviço")
    tipo_cod        = models.CharField(max_length=10,  blank=True, verbose_name="Código Tipo")
    setor           = models.CharField(max_length=50,  blank=True, verbose_name="Setor")
    logradouro      = models.CharField(max_length=300, verbose_name="Logradouro")
    referencia      = models.CharField(max_length=300, blank=True, verbose_name="Referência")
    nome_local      = models.CharField(max_length=300, blank=True, verbose_name="Nome do Local")

    latitude        = models.FloatField(null=True, blank=True)
    longitude       = models.FloatField(null=True, blank=True)

    data_inicio     = models.DateField(null=True, blank=True, verbose_name="Início vigência")
    data_fim        = models.DateField(null=True, blank=True, verbose_name="Fim vigência")
    horario_inicio  = models.CharField(max_length=10, blank=True)
    horario_fim     = models.CharField(max_length=10, blank=True)
    frequencia      = models.CharField(max_length=20, blank=True)
    turno           = models.CharField(max_length=5, blank=True)

    # Datas agendadas serializadas como "dd/mm/yyyy;dd/mm/yyyy;..."
    opcoes_data     = models.TextField(blank=True, verbose_name="Opções de data")

    qtd_operadores  = models.IntegerField(default=0)
    qtd_veiculos    = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Programação de Serviço"
        verbose_name_plural = "Programações de Serviços"
        ordering = ['subprefeitura', 'tipo_nome', 'setor']

    def __str__(self):
        return f"{self.subprefeitura} | {self.tipo_nome} | {self.setor} — {self.logradouro}"

    def datas_lista(self):
        """Retorna lista de strings de datas agendadas."""
        if not self.opcoes_data:
            return []
        return [d.strip() for d in self.opcoes_data.replace(' - ', ';').split(';') if d.strip()]

    def proximas_datas(self, n=5):
        """Retorna as próximas N datas a partir de hoje."""
        from datetime import date
        hoje = date.today()
        resultado = []
        for ds in self.datas_lista():
            for fmt in ('%d/%m/%Y', '%d/%m/%y'):
                try:
                    d = __import__('datetime').datetime.strptime(ds, fmt).date()
                    if d >= hoje:
                        resultado.append(d)
                    break
                except ValueError:
                    continue
        resultado.sort()
        return [d.strftime('%d/%m/%Y') for d in resultado[:n]]


class ImportacaoRelatorio(models.Model):
    """Registro de cada importação de relatório realizada."""

    arquivo_nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50, choices=[
        ('relatorio', 'Relatório Flip'),
        ('programados', 'Consultas Programadas'),
    ])
    total_registros = models.IntegerField(default=0)
    importado_em = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True)

    class Meta:
        verbose_name = "Importação"
        verbose_name_plural = "Importações"
        ordering = ['-importado_em']

    def __str__(self):
        return f"{self.arquivo_nome} - {self.importado_em:%d/%m/%Y %H:%M}"
