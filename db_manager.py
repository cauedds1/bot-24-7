# db_manager.py
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from zoneinfo import ZoneInfo

# 🇧🇷 HORÁRIO DE BRASÍLIA: Todas as operações de datetime usam timezone de Brasília
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

def agora_brasilia():
    """Retorna datetime atual no horário de Brasília"""
    return datetime.now(BRASILIA_TZ)

class DatabaseManager:
    """
    Gerenciador de banco de dados para armazenar análises completas de jogos.
    Evita refazer análises desnecessárias e economiza créditos da API.
    """

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            print("⚠️ DATABASE_URL não encontrado. Cache de análises desabilitado.")
            self.enabled = False
        else:
            self.enabled = True

    def _get_connection(self):
        """Cria conexão com o banco de dados"""
        if not self.enabled:
            return None
        return psycopg2.connect(self.database_url)

    def salvar_analise(self, fixture_id: int, dados_jogo: dict, analises: dict, stats: dict):
        """
        Salva análise completa de um jogo no banco de dados.

        Args:
            fixture_id: ID único do jogo na API-Football
            dados_jogo: Dict com {data_jogo, liga, time_casa, time_fora}
            analises: Dict com {gols, cantos, btts, resultado, cartoes, contexto}
            stats: Dict com {stats_casa, stats_fora, classificacao}
        """
        if not self.enabled:
            return False

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Contar total de palpites
            total_palpites = 0
            confiancas = []

            for mercado in ['gols', 'cantos', 'btts', 'resultado', 'cartoes']:
                if mercado in analises and analises[mercado]:
                    palpites = analises[mercado].get('palpites', [])
                    total_palpites += len(palpites)
                    for p in palpites:
                        confiancas.append(p.get('confianca', 0))

            confianca_media = round(sum(confiancas) / len(confiancas), 1) if confiancas else 0

            # INSERT ou UPDATE
            query = """
                INSERT INTO analises_jogos 
                (fixture_id, data_jogo, liga, time_casa, time_fora, 
                 stats_casa, stats_fora, classificacao,
                 analise_gols, analise_cantos, analise_btts, analise_resultado, analise_cartoes, analise_contexto,
                 palpites_totais, confianca_media, data_analise, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fixture_id) 
                DO UPDATE SET
                    stats_casa = EXCLUDED.stats_casa,
                    stats_fora = EXCLUDED.stats_fora,
                    classificacao = EXCLUDED.classificacao,
                    analise_gols = EXCLUDED.analise_gols,
                    analise_cantos = EXCLUDED.analise_cantos,
                    analise_btts = EXCLUDED.analise_btts,
                    analise_resultado = EXCLUDED.analise_resultado,
                    analise_cartoes = EXCLUDED.analise_cartoes,
                    analise_contexto = EXCLUDED.analise_contexto,
                    palpites_totais = EXCLUDED.palpites_totais,
                    confianca_media = EXCLUDED.confianca_media,
                    atualizado_em = EXCLUDED.atualizado_em
            """

            cursor.execute(query, (
                fixture_id,
                dados_jogo['data_jogo'],
                dados_jogo['liga'],
                dados_jogo['time_casa'],
                dados_jogo['time_fora'],
                Json(stats.get('stats_casa', {})),
                Json(stats.get('stats_fora', {})),
                Json(stats.get('classificacao', {})),
                Json(analises.get('gols', {})),
                Json(analises.get('cantos', {})),
                Json(analises.get('btts', {})),
                Json(analises.get('resultado', {})),
                Json(analises.get('cartoes', {})),
                Json(analises.get('contexto', {})),
                total_palpites,
                confianca_media,
                agora_brasilia(),
                agora_brasilia()
            ))

            conn.commit()
            cursor.close()
            conn.close()

            print(f"✅ Análise salva no banco: Fixture #{fixture_id} ({total_palpites} palpites)")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar análise no banco: {e}")
            return False

    def buscar_analise(self, fixture_id: int, max_idade_horas: int = 12) -> Optional[Dict]:
        """
        Busca análise existente no banco de dados.

        Args:
            fixture_id: ID único do jogo
            max_idade_horas: Idade máxima da análise em horas (padrão: 12h)

        Returns:
            Dict com a análise completa ou None se não encontrar
        """
        if not self.enabled:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Buscar apenas análises recentes
            limite_tempo = agora_brasilia() - timedelta(hours=max_idade_horas)

            query = """
                SELECT * FROM analises_jogos 
                WHERE fixture_id = %s 
                AND atualizado_em >= %s
            """

            cursor.execute(query, (fixture_id, limite_tempo))
            resultado = cursor.fetchone()

            cursor.close()
            conn.close()

            if resultado:
                # Converter de dict do psycopg2 para dict normal
                analise = dict(resultado)
                print(f"🎯 CACHE HIT (DB): Análise encontrada para Fixture #{fixture_id} ({analise['palpites_totais']} palpites)")
                return analise
            else:
                print(f"⚡ CACHE MISS (DB): Análise não encontrada para Fixture #{fixture_id}")
                return None

        except Exception as e:
            print(f"❌ Erro ao buscar análise no banco: {e}")
            return None

    def limpar_analises_antigas(self, dias: int = 7):
        """
        Remove análises antigas do banco de dados.

        Args:
            dias: Remover análises com mais de X dias (padrão: 7)
        """
        if not self.enabled:
            return 0

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            limite_tempo = agora_brasilia() - timedelta(days=dias)

            query = "DELETE FROM analises_jogos WHERE data_jogo < %s"
            cursor.execute(query, (limite_tempo,))

            deletados = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            print(f"🧹 Limpeza: {deletados} análises antigas removidas")
            return deletados

        except Exception as e:
            print(f"❌ Erro ao limpar análises antigas: {e}")
            return 0

    def obter_estatisticas_cache(self) -> Dict:
        """
        Retorna estatísticas sobre o cache de análises.
        """
        if not self.enabled:
            return {"enabled": False}

        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Total de análises
            cursor.execute("SELECT COUNT(*) as total FROM analises_jogos")
            total = cursor.fetchone()['total']

            # Análises de hoje
            cursor.execute("SELECT COUNT(*) as hoje FROM analises_jogos WHERE data_jogo = CURRENT_DATE")
            hoje = cursor.fetchone()['hoje']

            # Análises nas últimas 24h
            cursor.execute("SELECT COUNT(*) as recentes FROM analises_jogos WHERE atualizado_em >= NOW() - INTERVAL '24 hours'")
            recentes = cursor.fetchone()['recentes']

            cursor.close()
            conn.close()

            return {
                "enabled": True,
                "total_analises": total,
                "analises_hoje": hoje,
                "analises_24h": recentes
            }

        except Exception as e:
            print(f"❌ Erro ao obter estatísticas: {e}")
            return {"enabled": True, "erro": str(e)}

    def forcar_reanalisar(self, fixture_id: int):
        """
        Remove análise específica do cache, forçando reanálise.
        """
        if not self.enabled:
            return False

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM analises_jogos WHERE fixture_id = %s", (fixture_id,))

            conn.commit()
            cursor.close()
            conn.close()

            print(f"🔄 Análise do Fixture #{fixture_id} removida. Será reanalisado.")
            return True

        except Exception as e:
            print(f"❌ Erro ao forçar reanálise: {e}")
            return False
