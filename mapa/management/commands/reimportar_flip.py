"""
Comando para limpar todos os serviços importados e reimportar
os arquivos da pasta Flip com o encoding correto.

Uso:
    python manage.py reimportar_flip
    python manage.py reimportar_flip --pasta "C:/caminho/alternativo"
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from mapa.models import Servico, ImportacaoRelatorio
from mapa.importador import importar_relatorio_flip


PASTA_PADRAO = os.path.join(settings.BASE_DIR, 'Flip')


class Command(BaseCommand):
    help = 'Limpa serviços existentes e reimporta todos os arquivos da pasta Flip'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pasta',
            default=PASTA_PADRAO,
            help=f'Pasta com os arquivos Flip (padrão: {PASTA_PADRAO})',
        )

    def handle(self, *args, **options):
        pasta = options['pasta']

        if not os.path.isdir(pasta):
            self.stderr.write(self.style.ERROR(f'Pasta não encontrada: {pasta}'))
            return

        arquivos = [f for f in os.listdir(pasta)
                    if f.lower().endswith('.csv') or f.lower().endswith('.xlsx')]

        if not arquivos:
            self.stderr.write(self.style.ERROR('Nenhum arquivo .csv ou .xlsx encontrado na pasta.'))
            return

        # Limpa dados anteriores
        total_apagados = Servico.objects.count()
        Servico.objects.all().delete()
        ImportacaoRelatorio.objects.filter(tipo='relatorio').delete()
        self.stdout.write(f'  {total_apagados} registros apagados.')

        # Reimporta
        total_geral = 0
        for fname in sorted(arquivos):
            path = os.path.join(pasta, fname)
            with open(path, 'rb') as f:
                class ArquivoWrapper:
                    name = fname
                    def read(self_):
                        return f.read()

                total = importar_relatorio_flip(ArquivoWrapper())
                total_geral += total
                self.stdout.write(f'  {fname}: {total} registros')

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído: {total_geral} serviços importados de {len(arquivos)} arquivo(s).'
        ))
