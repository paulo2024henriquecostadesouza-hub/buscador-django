"""
Baixa os limites oficiais das regionais de atuação diretamente do GeoSampa
(Prefeitura de São Paulo) e salva em data/regioes.json.

Fonte: http://wfs.geosampa.prefeitura.sp.gov.br — camada distrito_municipal

Uso:
    python manage.py baixar_regioes
"""
import json
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


SUBPREFEITURAS = {
    'IPIRANGA':      '#3b82f6',  # azul   — inclui Ipiranga, Cursino, Sacoma
    'JABAQUARA':     '#22c55e',  # verde
    'CIDADE ADEMAR': '#f97316',  # laranja — inclui Cidade Ademar, Pedreira
}

DESTINO = Path(settings.BASE_DIR) / 'data' / 'regioes.json'

WFS_URL = (
    'http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs'
    '?service=WFS&version=2.0.0&request=GetFeature'
    '&typeName=geoportal:subprefeitura'
    '&outputFormat=application/json'
    '&srsName=EPSG:4326'
)


class Command(BaseCommand):
    help = 'Baixa limites oficiais das regionais do GeoSampa (Prefeitura SP)'

    def handle(self, *args, **options):
        self.stdout.write('Conectando ao GeoSampa...')
        req = urllib.request.Request(WFS_URL, headers={'User-Agent': 'BuscadorDjango/1.0'})

        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erro ao conectar ao GeoSampa: {e}'))
            return

        total = len(data.get('features', []))
        self.stdout.write(f'  {total} distritos recebidos.')

        features = []
        for feat in data['features']:
            nome = feat['properties'].get('nm_subprefeitura', '')
            if nome in SUBPREFEITURAS:
                feat['properties'] = {
                    'nome': nome.title(),
                    'cor': SUBPREFEITURAS[nome],
                }
                features.append(feat)
                self.stdout.write(f'  OK: {nome.title()} ({feat["geometry"]["type"]})')

        if not features:
            self.stderr.write(self.style.ERROR('Nenhuma subprefeitura encontrada. Verifique os nomes.'))
            return

        DESTINO.parent.mkdir(exist_ok=True)
        DESTINO.write_text(
            json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False),
            encoding='utf-8'
        )
        self.stdout.write(self.style.SUCCESS(
            f'\nSalvo em {DESTINO} com {len(features)} regional(is) — fonte: GeoSampa/Prefeitura SP'
        ))
