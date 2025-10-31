#!/usr/bin/env python3
"""
🎯 TRACER BULLET DEBUG - CRITICAL DATA INTEGRITY INVESTIGATION
Este script executa análise super-verbose de UM único fixture da Eredivisie
para identificar o bug sistêmico de perda de dados.

Fixture de Teste: 1376437 (Willem II vs Telstar - Eredivisie)
"""

import asyncio
import sys
import os
from api_client import (
    buscar_estatisticas_jogo,
    buscar_estatisticas_gerais_time,
    buscar_ultimos_jogos_time,
    buscar_classificacao_liga,
    get_current_season,
    api_request_with_retry,
    API_URL
)

# 🎯 FIXTURE DE TESTE - HARDCODED
TARGET_FIXTURE_ID = 1376437  # Willem II vs Telstar - Eredivisie
TARGET_LEAGUE_ID = 88  # Eredivisie


async def main():
    """Executa análise super-verbose do fixture de teste"""
    
    print("=" * 80)
    print("🎯 TRACER BULLET DEBUG - DATA INTEGRITY INVESTIGATION")
    print("=" * 80)
    print(f"\nFixture ID: {TARGET_FIXTURE_ID}")
    print(f"Liga: Eredivisie (ID: {TARGET_LEAGUE_ID})")
    print(f"Objetivo: Rastrear pipeline completo de dados para identificar ponto de falha\n")
    print("=" * 80)
    
    try:
        # Passo 1: Buscar detalhes básicos do jogo
        print("\n[PASSO 1/6] 🔍 Buscando detalhes básicos do jogo...")
        print("-" * 80)
        
        # Chamar API diretamente para pegar detalhes do fixture
        params = {"id": str(TARGET_FIXTURE_ID)}
        response = await api_request_with_retry("GET", API_URL + "fixtures", params=params)
        response.raise_for_status()
        
        response_json = response.json()
        fixtures_data = response_json.get('response', [])
        
        if not fixtures_data or len(fixtures_data) == 0:
            print(f"❌ FALHA CRÍTICA: Fixture {TARGET_FIXTURE_ID} não encontrado na API")
            print(f"   Response: {response_json}")
            return
        
        detalhes_jogo = fixtures_data[0]
        
        home_team_id = detalhes_jogo['teams']['home']['id']
        away_team_id = detalhes_jogo['teams']['away']['id']
        home_team_name = detalhes_jogo['teams']['home']['name']
        away_team_name = detalhes_jogo['teams']['away']['name']
        fixture_date = detalhes_jogo['fixture']['date']
        fixture_status = detalhes_jogo['fixture']['status']['short']
        
        print(f"✅ Detalhes obtidos:")
        print(f"   Casa: {home_team_name} (ID: {home_team_id})")
        print(f"   Fora: {away_team_name} (ID: {away_team_id})")
        print(f"   Data: {fixture_date}")
        print(f"   Status: {fixture_status}")
        
        # Passo 2: Buscar estatísticas do jogo
        print("\n[PASSO 2/6] 📊 Buscando estatísticas do jogo...")
        print("-" * 80)
        stats_jogo = await buscar_estatisticas_jogo(TARGET_FIXTURE_ID)
        
        if stats_jogo:
            print(f"✅ Estatísticas do jogo obtidas:")
            print(f"   Cantos Casa: {stats_jogo.get('home', {}).get('Corner Kicks', 'N/A')}")
            print(f"   Cantos Fora: {stats_jogo.get('away', {}).get('Corner Kicks', 'N/A')}")
            print(f"   Finalizações Casa: {stats_jogo.get('home', {}).get('Total Shots', 'N/A')}")
            print(f"   Finalizações Fora: {stats_jogo.get('away', {}).get('Total Shots', 'N/A')}")
        else:
            print("❌ FALHA: Estatísticas do jogo não obtidas")
        
        # Passo 3: Detectar temporada atual
        print("\n[PASSO 3/6] 📅 Detectando temporada atual da liga...")
        print("-" * 80)
        season = await get_current_season(TARGET_LEAGUE_ID)
        print(f"✅ Temporada detectada: {season}")
        
        # Passo 4: Buscar estatísticas gerais do time da casa
        print(f"\n[PASSO 4/6] 📈 Buscando estatísticas gerais - {home_team_name}...")
        print("-" * 80)
        stats_casa = await buscar_estatisticas_gerais_time(home_team_id, TARGET_LEAGUE_ID)
        
        if stats_casa:
            print(f"\n✅ Estatísticas gerais obtidas para {home_team_name}:")
            print(f"   Gols marcados (casa): {stats_casa.get('casa', {}).get('gols_marcados', 'N/A')}")
            print(f"   Cantos feitos (casa): {stats_casa.get('casa', {}).get('cantos_feitos', 'N/A')}")
            print(f"   Finalizações (casa): {stats_casa.get('casa', {}).get('finalizacoes', 'N/A')}")
        else:
            print(f"❌ FALHA: Estatísticas gerais não obtidas para {home_team_name}")
        
        # Passo 5: Buscar estatísticas gerais do time visitante
        print(f"\n[PASSO 5/6] 📈 Buscando estatísticas gerais - {away_team_name}...")
        print("-" * 80)
        stats_fora = await buscar_estatisticas_gerais_time(away_team_id, TARGET_LEAGUE_ID)
        
        if stats_fora:
            print(f"\n✅ Estatísticas gerais obtidas para {away_team_name}:")
            print(f"   Gols marcados (fora): {stats_fora.get('fora', {}).get('gols_marcados', 'N/A')}")
            print(f"   Cantos feitos (fora): {stats_fora.get('fora', {}).get('cantos_feitos', 'N/A')}")
            print(f"   Finalizações (fora): {stats_fora.get('fora', {}).get('finalizacoes', 'N/A')}")
        else:
            print(f"❌ FALHA: Estatísticas gerais não obtidas para {away_team_name}")
        
        # Passo 6: Buscar classificação da liga
        print(f"\n[PASSO 6/6] 🏆 Buscando classificação da liga...")
        print("-" * 80)
        classificacao = await buscar_classificacao_liga(TARGET_LEAGUE_ID)
        
        if classificacao:
            print(f"✅ Classificação obtida: {len(classificacao)} times")
        else:
            print("❌ FALHA: Classificação não obtida")
        
        # Resumo Final
        print("\n" + "=" * 80)
        print("📋 RESUMO DA INVESTIGAÇÃO")
        print("=" * 80)
        
        passos_ok = 0
        passos_falha = 0
        
        checks = [
            ("Detalhes do jogo", detalhes_jogo is not None),
            ("Estatísticas do jogo", stats_jogo is not None),
            ("Temporada detectada", season is not None),
            (f"Stats gerais {home_team_name}", stats_casa is not None),
            (f"Stats gerais {away_team_name}", stats_fora is not None),
            ("Classificação da liga", classificacao is not None)
        ]
        
        for nome, status in checks:
            if status:
                print(f"✅ {nome}")
                passos_ok += 1
            else:
                print(f"❌ {nome}")
                passos_falha += 1
        
        print(f"\nTotal: {passos_ok}/6 passos OK, {passos_falha}/6 falhas")
        
        if passos_falha > 0:
            print("\n🚨 BUGS IDENTIFICADOS - Revisar logs acima para detalhes específicos")
        else:
            print("\n✅ Todos os passos OK - Pipeline de dados funcionando corretamente")
        
    except Exception as e:
        print(f"\n❌ ERRO FATAL durante investigação:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("🏁 INVESTIGAÇÃO CONCLUÍDA")
    print("=" * 80)


if __name__ == "__main__":
    # Inicializar HTTP client
    asyncio.run(main())
