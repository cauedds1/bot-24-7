# db_manager.py
import os
import json
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from zoneinfo import ZoneInfo
from contextlib import contextmanager

# 🇧🇷 HORÁRIO DE BRASÍLIA: Todas as operações de datetime usam timezone de Brasília
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

def agora_brasilia():
    """Retorna datetime atual no horário de Brasília"""
    return datetime.now(BRASILIA_TZ)

class DatabaseManager:
    """
    Gerenciador de banco de dados para armazenar análises completas de jogos.
    Evita refazer análises desnecessárias e economiza créditos da API.
    Usa connection pooling para melhor performance e eficiência.
    """

    def __init__(self, min_conn=1, max_conn=10):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            print("⚠️ DATABASE_URL não encontrado. Cache de análises desabilitado.")
            self.enabled = False
            self.pool = None
        else:
            self.enabled = True
            try:
                # Criar connection pool
                self.pool = psycopg2.pool.SimpleConnectionPool(
                    min_conn,
                    max_conn,
                    self.database_url
                )
                print(f"✅ Connection pool criado: {min_conn}-{max_conn} conexões")
            except Exception as e:
                print(f"❌ Erro ao criar connection pool: {e}")
                self.enabled = False
                self.pool = None

    @contextmanager
    def _get_connection(self):
        """Context manager para obter conexão do pool"""
        if not self.enabled or not self.pool:
            yield None
            return
        
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def initialize_database(self):
        """
        Inicializa o schema do banco de dados, criando todas as tabelas necessárias.
        Executa CREATE TABLE IF NOT EXISTS para garantir que o schema está completo.
        """
        if not self.enabled:
            print("⚠️ Database não habilitado, pulando inicialização")
            return False
        
        schema_sql = """
        -- Tabela principal de análises de jogos (cache)
        CREATE TABLE IF NOT EXISTS analises_jogos (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER UNIQUE NOT NULL,
            data_jogo TIMESTAMP WITH TIME ZONE NOT NULL,
            liga VARCHAR(255),
            time_casa VARCHAR(255),
            time_fora VARCHAR(255),
            stats_casa JSONB,
            stats_fora JSONB,
            classificacao JSONB,
            analise_gols JSONB,
            analise_cantos JSONB,
            analise_btts JSONB,
            analise_resultado JSONB,
            analise_cartoes JSONB,
            analise_contexto JSONB,
            palpites_totais INTEGER DEFAULT 0,
            confianca_media DECIMAL(3,1) DEFAULT 0,
            data_analise TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Índices para performance
        CREATE INDEX IF NOT EXISTS idx_analises_jogos_fixture_id ON analises_jogos(fixture_id);
        CREATE INDEX IF NOT EXISTS idx_analises_jogos_data_jogo ON analises_jogos(data_jogo);
        CREATE INDEX IF NOT EXISTS idx_analises_jogos_atualizado_em ON analises_jogos(atualizado_em);

        -- Nova tabela para sistema de fila de análises diárias
        CREATE TABLE IF NOT EXISTS daily_analyses (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER NOT NULL,
            analysis_type VARCHAR(50) NOT NULL,
            dossier_json TEXT NOT NULL,
            user_id BIGINT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT daily_analyses_unique UNIQUE (fixture_id, analysis_type, user_id)
        );

        -- Índices para performance na tabela daily_analyses
        CREATE INDEX IF NOT EXISTS idx_daily_analyses_user_type ON daily_analyses(user_id, analysis_type);
        CREATE INDEX IF NOT EXISTS idx_daily_analyses_created_at ON daily_analyses(created_at);
        CREATE INDEX IF NOT EXISTS idx_daily_analyses_fixture_id ON daily_analyses(fixture_id);
        
        -- Comentários para documentação
        COMMENT ON TABLE analises_jogos IS 'Cache de análises completas de jogos processados';
        COMMENT ON TABLE daily_analyses IS 'Análises processadas em batch pelo sistema de fila assíncrona';
        COMMENT ON COLUMN daily_analyses.analysis_type IS 'Tipo: full, goals_only, corners_only, btts_only, result_only, simple_bet, multiple_bet, bingo';
        COMMENT ON COLUMN daily_analyses.dossier_json IS 'JSON completo do dossier de análise gerado pelo master_analyzer';
        """
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    print("❌ Não foi possível obter conexão para inicializar banco")
                    return False
                
                cursor = conn.cursor()
                
                # Executar todo o schema
                cursor.execute(schema_sql)
                
                conn.commit()
                cursor.close()
                
                print("✅ Database schema inicializado com sucesso!")
                print("   📋 Tabelas criadas: analises_jogos, daily_analyses")
                return True
                
        except Exception as e:
            print(f"❌ Erro ao inicializar database schema: {e}")
            return False
    
    def close_pool(self):
        """Fecha o connection pool ao desligar a aplicação"""
        if self.pool:
            self.pool.closeall()
            print("✅ Connection pool fechado")

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
            with self._get_connection() as conn:
                if not conn:
                    return False
                    
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
            with self._get_connection() as conn:
                if not conn:
                    return None
                    
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
            with self._get_connection() as conn:
                if not conn:
                    return 0
                    
                cursor = conn.cursor()

                limite_tempo = agora_brasilia() - timedelta(days=dias)

                query = "DELETE FROM analises_jogos WHERE data_jogo < %s"
                cursor.execute(query, (limite_tempo,))

                deletados = cursor.rowcount
                conn.commit()
                cursor.close()

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
            with self._get_connection() as conn:
                if not conn:
                    return {"enabled": True, "erro": "Conexão não disponível"}
                    
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
            with self._get_connection() as conn:
                if not conn:
                    return False
                    
                cursor = conn.cursor()

                cursor.execute("DELETE FROM analises_jogos WHERE fixture_id = %s", (fixture_id,))

                conn.commit()
                cursor.close()

                print(f"🔄 Análise do Fixture #{fixture_id} removida. Será reanalisado.")
                return True

        except Exception as e:
            print(f"❌ Erro ao forçar reanálise: {e}")
            return False

    def save_daily_analysis(self, fixture_id: int, analysis_type: str, dossier_json: str, user_id: int):
        """
        Salva análise processada em batch no sistema de fila.
        
        Args:
            fixture_id: ID do jogo
            analysis_type: Tipo de análise ('full', 'goals_only', 'corners_only', etc.')
            dossier_json: JSON completo da análise (dossier)
            user_id: ID do usuário que solicitou
        """
        if not self.enabled:
            return False
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    return False
                    
                cursor = conn.cursor()
                
                query = """
                    INSERT INTO daily_analyses 
                    (fixture_id, analysis_type, dossier_json, user_id, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (fixture_id, analysis_type, user_id)
                    DO UPDATE SET
                        dossier_json = EXCLUDED.dossier_json,
                        created_at = EXCLUDED.created_at
                """
                
                cursor.execute(query, (
                    fixture_id,
                    analysis_type,
                    dossier_json,
                    user_id,
                    agora_brasilia()
                ))
                
                conn.commit()
                cursor.close()
                return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar daily analysis: {e}")
            return False
    
    def get_daily_analyses(self, user_id: int, analysis_type: str, offset: int = 0, limit: int = 5) -> List[Dict]:
        """
        Recupera análises paginadas do banco.
        
        Args:
            user_id: ID do usuário
            analysis_type: Tipo de análise
            offset: Offset para paginação
            limit: Limite de resultados
            
        Returns:
            Lista de análises com seus dossiers
        """
        if not self.enabled:
            return []
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    return []
                    
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                query = """
                    SELECT id, fixture_id, analysis_type, dossier_json, created_at
                    FROM daily_analyses
                    WHERE user_id = %s AND analysis_type = %s
                    AND created_at >= CURRENT_DATE
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                cursor.execute(query, (user_id, analysis_type, limit, offset))
                resultados = cursor.fetchall()
                
                cursor.close()
                
                return [dict(r) for r in resultados]
            
        except Exception as e:
            print(f"❌ Erro ao buscar daily analyses: {e}")
            return []
    
    def count_daily_analyses(self, user_id: int, analysis_type: str) -> int:
        """
        Conta total de análises disponíveis para paginação.
        
        Args:
            user_id: ID do usuário
            analysis_type: Tipo de análise
            
        Returns:
            Total de análises
        """
        if not self.enabled:
            return 0
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    return 0
                    
                cursor = conn.cursor()
                
                query = """
                    SELECT COUNT(*) as total
                    FROM daily_analyses
                    WHERE user_id = %s AND analysis_type = %s
                    AND created_at >= CURRENT_DATE
                """
                
                cursor.execute(query, (user_id, analysis_type))
                total = cursor.fetchone()[0]
                
                cursor.close()
                
                return total
            
        except Exception as e:
            print(f"❌ Erro ao contar daily analyses: {e}")
            return 0
