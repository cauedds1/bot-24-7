"""
PHOENIX V3.0 - EVIDENCE-BASED ANALYSIS PROTOCOL
================================================

Formatador de mensagens implementando o protocolo Evidence-Based Analysis.

ESTRUTURA OBRIGATÓRIA DO OUTPUT:
1. 🏆 Header: Liga, Times (Posições), Data/Hora
2. 💎 ANÁLISE PRINCIPAL: Melhor palpite com evidências dos últimos 4 jogos
3. 🧠 SUGESTÕES TÁTICAS: Outras análises de valor (com ou sem odds)
4. ⚠️ AVISOS: Mercados sem odds ou análises indisponíveis
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from analysts.justification_generator import generate_evidence_based_justification


def format_evidence_based_dossier(
    jogo: Dict,
    todos_palpites: List[Dict],
    master_analysis: Dict
) -> str:
    """
    EVIDENCE-BASED PROTOCOL: Formata mensagem seguindo especificação exata.
    
    Args:
        jogo: Dados do jogo
        todos_palpites: TODOS os palpites (com e sem odd), ordenados por confiança desc
        master_analysis: Análise completa do Master Analyzer (com evidências)
    
    Returns:
        str: Mensagem formatada em Plain Text seguindo protocolo Evidence-Based
    """
    if not todos_palpites or len(todos_palpites) == 0:
        return _format_header_evidence_based(jogo) + "\n⚠️ Nenhuma análise de valor identificada para este jogo.\n"
    
    # Extrair dados
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    evidence = master_analysis.get('evidence', {})
    evidencias_home = evidence.get('home', {})
    evidencias_away = evidence.get('away', {})
    home_team_name = evidence.get('home_team_name', time_casa)
    away_team_name = evidence.get('away_team_name', time_fora)
    
    # === SECTION 1: HEADER ===
    msg = _format_header_evidence_based(jogo)
    
    # === SECTION 2: ANÁLISE PRINCIPAL ===
    palpite_principal = todos_palpites[0]  # Maior confiança
    msg += _format_analise_principal_evidence_based(
        palpite_principal, 
        evidencias_home, 
        evidencias_away,
        home_team_name,
        away_team_name
    )
    
    # === SECTION 3: SUGESTÕES TÁTICAS (restante dos palpites) ===
    if len(todos_palpites) > 1:
        msg += _format_sugestoes_taticas_evidence_based(
            todos_palpites[1:], 
            evidencias_home, 
            evidencias_away,
            home_team_name,
            away_team_name
        )
    
    # === SECTION 4: AVISOS (se houver) ===
    avisos = _collect_warnings(todos_palpites)
    if avisos:
        msg += _format_avisos(avisos)
    
    return msg


def _format_header_evidence_based(jogo: Dict) -> str:
    """Formata header conforme especificação Evidence-Based"""
    liga_nome = jogo['league']['name']
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    
    # Converter horário UTC para Brasília
    data_utc = datetime.strptime(jogo['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
    data_brasilia = data_utc - timedelta(hours=3)
    data_formatada = data_brasilia.strftime('%d/%m/%Y')
    horario_formatado = data_brasilia.strftime('%H:%M')
    
    msg = f"🏆 {liga_nome}\n"
    msg += f"⚽ {time_casa} vs {time_fora}\n"
    msg += f"⏰ {data_formatada} às {horario_formatado} (Brasília)\n"
    msg += f"---\n\n"
    
    return msg


def _format_analise_principal_evidence_based(
    palpite: Dict,
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """Formata ANÁLISE PRINCIPAL com evidências dos últimos 4 jogos"""
    mercado = palpite.get('mercado', 'Gols')
    tipo = palpite.get('tipo', '')
    confianca = palpite.get('confianca', 0)
    odd = palpite.get('odd')
    
    msg = f"💎 ANÁLISE PRINCIPAL\n"
    msg += f"   Mercado: {mercado}\n"
    
    # Formatar palpite
    palpite_str = f"{tipo}"
    if odd and odd > 0:
        palpite_str += f" @{odd:.2f}"
    msg += f"   Palpite: {palpite_str}\n"
    msg += f"   Confiança: {confianca:.1f} / 10\n"
    
    # Justificativa baseada em evidências
    msg += f"   Justificativa: "
    justificativa = generate_evidence_based_justification(
        mercado, tipo, evidencias_home, evidencias_away, home_team_name, away_team_name
    )
    msg += justificativa + "\n\n"
    
    # === EVIDÊNCIAS DOS ÚLTIMOS 4 JOGOS ===
    msg += f"   📊 EVIDÊNCIAS (ÚLTIMOS 4 JOGOS):\n"
    msg += _format_evidence_section(mercado, evidencias_home, evidencias_away, home_team_name, away_team_name)
    
    msg += f"---\n\n"
    return msg


def _format_evidence_section(
    mercado: str,
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """Formata seção de evidências conforme o mercado"""
    msg = ""
    
    if mercado == "Gols":
        msg += _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Cantos":
        msg += _format_cantos_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Cartões":
        msg += _format_cartoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Finalizações":
        msg += _format_finalizacoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    else:
        msg += f"      (Evidências não disponíveis para este mercado)\n"
    
    return msg


def _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de GOLS dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    gols_home = evidencias_home.get('gols', [])
    if gols_home:
        for jogo in gols_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '0-0')
            total = jogo.get('total_goals', 0)
            msg += f"         vs {opponent}: {result} (Total: {total})\n"
        
        # Calcular média
        media = sum(j['total_goals'] for j in gols_home) / len(gols_home)
        msg += f"         📈 Média Gols (Jogos): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    gols_away = evidencias_away.get('gols', [])
    if gols_away:
        for jogo in gols_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '0-0')
            total = jogo.get('total_goals', 0)
            msg += f"         vs {opponent}: {result} (Total: {total})\n"
        
        # Calcular média
        media = sum(j['total_goals'] for j in gols_away) / len(gols_away)
        msg += f"         📉 Média Gols (Jogos): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_cantos_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de CANTOS dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    cantos_home = evidencias_home.get('cantos', [])
    if cantos_home:
        for jogo in cantos_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            corners_for = jogo.get('corners_for', 0)
            total = jogo.get('total_corners', 0)
            msg += f"         vs {opponent}: {corners_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['corners_for'] for j in cantos_home) / len(cantos_home)
        msg += f"         📈 Média Cantos (Próprios): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    cantos_away = evidencias_away.get('cantos', [])
    if cantos_away:
        for jogo in cantos_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            corners_for = jogo.get('corners_for', 0)
            total = jogo.get('total_corners', 0)
            msg += f"         vs {opponent}: {corners_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['corners_for'] for j in cantos_away) / len(cantos_away)
        msg += f"         📈 Média Cantos (Próprios): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_cartoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de CARTÕES dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    cartoes_home = evidencias_home.get('cartoes', [])
    if cartoes_home:
        for jogo in cartoes_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            total_cards = jogo.get('total_cards', 0)
            msg += f"         vs {opponent}: {total_cards} cartões\n"
        
        # Calcular média
        media = sum(j['total_cards'] for j in cartoes_home) / len(cartoes_home)
        msg += f"         📈 Média Cartões: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    cartoes_away = evidencias_away.get('cartoes', [])
    if cartoes_away:
        for jogo in cartoes_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            total_cards = jogo.get('total_cards', 0)
            msg += f"         vs {opponent}: {total_cards} cartões\n"
        
        # Calcular média
        media = sum(j['total_cards'] for j in cartoes_away) / len(cartoes_away)
        msg += f"         📈 Média Cartões: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_finalizacoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de FINALIZAÇÕES dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    shots_home = evidencias_home.get('finalizacoes', [])
    if shots_home:
        for jogo in shots_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            shots_for = jogo.get('shots_for', 0)
            total = jogo.get('total_shots', 0)
            msg += f"         vs {opponent}: {shots_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['shots_for'] for j in shots_home) / len(shots_home)
        msg += f"         📈 Média Finalizações: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    shots_away = evidencias_away.get('finalizacoes', [])
    if shots_away:
        for jogo in shots_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            shots_for = jogo.get('shots_for', 0)
            total = jogo.get('total_shots', 0)
            msg += f"         vs {opponent}: {shots_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['shots_for'] for j in shots_away) / len(shots_away)
        msg += f"         📈 Média Finalizações: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_sugestoes_taticas_evidence_based(
    palpites: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """Formata SUGESTÕES TÁTICAS com evidências (todas as outras análises)"""
    if not palpites:
        return ""
    
    msg = f"🧠 SUGESTÕES TÁTICAS (OUTRAS ANÁLISES DE VALOR)\n\n"
    
    for palpite in palpites[:5]:  # Máximo 5 sugestões adicionais
        mercado = palpite.get('mercado', 'Gols')
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        odd = palpite.get('odd')
        
        msg += f"   Mercado: {mercado}\n"
        
        # Análise
        analise_str = f"{tipo}"
        if odd and odd > 0:
            analise_str += f" @{odd:.2f}"
        else:
            analise_str += " (sem odd disponível)"
        msg += f"   Análise: {analise_str}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        
        # Justificativa
        justificativa = generate_evidence_based_justification(
            mercado, tipo, evidencias_home, evidencias_away, home_team_name, away_team_name
        )
        msg += f"   Justificativa: {justificativa}\n\n"
        
        # Evidências resumidas (apenas médias)
        msg += f"   📊 EVIDÊNCIAS:\n"
        msg += _format_evidence_summary(mercado, evidencias_home, evidencias_away, home_team_name, away_team_name)
        msg += f"\n---\n\n"
    
    return msg


def _format_evidence_summary(mercado, evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata resumo de evidências (apenas médias)"""
    msg = ""
    
    if mercado == "Gols":
        gols_home = evidencias_home.get('gols', [])
        gols_away = evidencias_away.get('gols', [])
        if gols_home and gols_away:
            media_home = sum(j['total_goals'] for j in gols_home) / len(gols_home)
            media_away = sum(j['total_goals'] for j in gols_away) / len(gols_away)
            msg += f"      {home_team_name}: {media_home:.1f} gols/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} gols/jogo (fora)\n"
    
    elif mercado == "Cantos":
        cantos_home = evidencias_home.get('cantos', [])
        cantos_away = evidencias_away.get('cantos', [])
        if cantos_home and cantos_away:
            media_home = sum(j['corners_for'] for j in cantos_home) / len(cantos_home)
            media_away = sum(j['corners_for'] for j in cantos_away) / len(cantos_away)
            msg += f"      {home_team_name}: {media_home:.1f} cantos/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} cantos/jogo (fora)\n"
    
    elif mercado == "Cartões":
        cartoes_home = evidencias_home.get('cartoes', [])
        cartoes_away = evidencias_away.get('cartoes', [])
        if cartoes_home and cartoes_away:
            media_home = sum(j['total_cards'] for j in cartoes_home) / len(cartoes_home)
            media_away = sum(j['total_cards'] for j in cartoes_away) / len(cartoes_away)
            msg += f"      {home_team_name}: {media_home:.1f} cartões/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} cartões/jogo (fora)\n"
    
    elif mercado == "Finalizações":
        shots_home = evidencias_home.get('finalizacoes', [])
        shots_away = evidencias_away.get('finalizacoes', [])
        if shots_home and shots_away:
            media_home = sum(j['shots_for'] for j in shots_home) / len(shots_home)
            media_away = sum(j['shots_for'] for j in shots_away) / len(shots_away)
            msg += f"      {home_team_name}: {media_home:.1f} finalizações/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} finalizações/jogo (fora)\n"
    
    return msg


def _collect_warnings(palpites: List[Dict]) -> List[str]:
    """Coleta avisos sobre mercados sem odds ou análises indisponíveis"""
    avisos = []
    
    # Verificar se há palpites sem odd
    palpites_sem_odd = [p for p in palpites if not p.get('odd') or p.get('odd') == 0]
    if palpites_sem_odd:
        mercados_sem_odd = list(set(p.get('mercado', 'Desconhecido') for p in palpites_sem_odd))
        for mercado in mercados_sem_odd:
            avisos.append(f"⚠️ Nenhuma odd encontrada na API para o mercado de {mercado}.")
    
    return avisos


def _format_avisos(avisos: List[str]) -> str:
    """Formata seção de avisos"""
    if not avisos:
        return ""
    
    msg = f"⚠️ AVISOS E OBSERVAÇÕES\n"
    for aviso in avisos:
        msg += f"   {aviso}\n"
    msg += "\n"
    
    return msg


# Manter compatibilidade com código existente
def format_phoenix_dossier(*args, **kwargs):
    """Wrapper para compatibilidade"""
    return format_evidence_based_dossier(*args, **kwargs)


def format_dossier_message(*args, **kwargs):
    """Wrapper para compatibilidade"""
    return format_evidence_based_dossier(*args, **kwargs)
