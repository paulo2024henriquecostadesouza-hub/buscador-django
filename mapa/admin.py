from django.contrib import admin
from .models import Servico, ConsultaProgramada, ImportacaoRelatorio


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('tipo_servico', 'status', 'endereco', 'data_execucao', 'geocodificado')
    list_filter = ('status', 'tipo_servico', 'cidade')
    search_fields = ('endereco', 'numero_os', 'tipo_servico')
    readonly_fields = ('criado_em',)

    def geocodificado(self, obj):
        return "✓" if obj.geocodificado else "✗"
    geocodificado.short_description = "Geocodificado"


@admin.register(ConsultaProgramada)
class ConsultaProgramadaAdmin(admin.ModelAdmin):
    list_display = ('tipo_servico', 'endereco', 'data_programada', 'geocodificado')
    list_filter = ('tipo_servico',)
    search_fields = ('endereco',)

    def geocodificado(self, obj):
        return "✓" if obj.geocodificado else "✗"
    geocodificado.short_description = "Geocodificado"


@admin.register(ImportacaoRelatorio)
class ImportacaoRelatorioAdmin(admin.ModelAdmin):
    list_display = ('arquivo_nome', 'tipo', 'total_registros', 'importado_em')
    readonly_fields = ('importado_em',)
