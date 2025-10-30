"""
PHOENIX V3.0 - DOSSIÊ DO ANALISTA
==================================

Formatador de mensagens profissionais implementando EXATAMENTE o Phoenix Protocol.

ESTRUTURA DA MENSAGEM (OBRIGATÓRIA):
1. 🏆 Header: Liga, Data, Horário, Confronto
2. 📖 Roteiro Tático: Script selecionado + raciocínio
3. 💎 ANÁLISE PRINCIPAL: Tip com maior confiança (com/sem odd)
   - Se SEM odd: título muda para "ANÁLISE PRINCIPAL (OPORTUNIDADE TÁT ICA)"
4. 🧠 SUGESTÕES TÁTICAS: Outros tips SEM odd (alta confiança mas sem mercado)
5. 🎯 PALPITES ALTERNATIVOS: Outros tips COM odd (menor confiança)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


def format_phoenix_dossier(
    jogo: Dict,
    todos_palpites: List[Dict],
    stats_casa: Dict,
    stats_fora: Dict,
    master_analysis: Dict,
    ultimos_jogos_casa: Optional[List[Dict]] = None,
    ultimos_jogos_fora: Optional[List[Dict]] = None
) -> str:
    """
    PHOENIX V3.0: Formata mensagem seguindo o Phoenix Protocol exato.
    
    Args:
        jogo: Dados do jogo
        todos_palpites: TODOS os palpites (com e sem odd), ordenados por confiança desc
        stats_casa: Estatísticas time casa
        stats_fora: Estatísticas time fora
        master_analysis: Análise completa do Master Analyzer (com script e reasoning)
        ultimos_jogos_casa: Últimos jogos do time casa
        ultimos_jogos_fora: Últimos jogos do time fora
    
    Returns:
        str: Mensagem formatada em HTML seguindo Phoenix Protocol
    """
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    
    # === SECTION 1: HEADER ===
    msg = _format_header(jogo)
    
    # === SECTION 2: ROTEIRO TÁTICO ===
    msg += _format_tactical_script(master_analysis, time_casa, time_fora)
    
    # === SEPARAR PALPITES: Principal, Táticos sem odd, Alternativos com odd ===
    # O palpite principal é SEMPRE o de maior confiança (com ou sem odd)
    if not todos_palpites or len(todos_palpites) == 0:
        return msg + "\n⚠️ Nenhuma análise de valor identificada para este jogo.\n"
    
    palpite_principal = todos_palpites[0]  # Maior confiança
    restantes = todos_palpites[1:]
    
    # Separar restantes em: táticos (sem odd) e alternativos (com odd)
    sugestoes_taticas = [p for p in restantes if p.get('odd') is None or p.get('odd') == 0]
    palpites_alternativos = [p for p in restantes if p.get('odd') is not None and p.get('odd') > 0]
    
    # === SECTION 3: ANÁLISE PRINCIPAL ===
    msg += _format_analise_principal(
        palpite_principal, stats_casa, stats_fora, 
        time_casa, time_fora, master_analysis,
        ultimos_jogos_casa, ultimos_jogos_fora
    )
    
    # === SECTION 4: SUGESTÕES TÁTICAS (sem odd) ===
    if sugestoes_taticas:
        msg += _format_sugestoes_taticas(sugestoes_taticas)
    
    # === SECTION 5: PALPITES ALTERNATIVOS (com odd) ===
    if palpites_alternativos:
        msg += _format_palpites_alternativos(palpites_alternativos)
    
    return msg


def _format_header(jogo: Dict) -> str:
    """Formata header do jogo."""
    liga_nome = jogo['league']['name']
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    
    # Converter horário UTC para Brasília
    data_utc = datetime.strptime(jogo['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
    data_brasilia = data_utc - timedelta(hours=3)
    data_formatada = data_brasilia.strftime('%d/%m/%Y')
    horario_formatado = data_brasilia.strftime('%H:%M')
    
    msg = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏆 <b>{liga_nome}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"📅 <b>Data:</b> {data_formatada}\n"
    msg += f"🕐 <b>Horário:</b> {horario_formatado} (Brasília)\n"
    msg += f"⚽ <b>Confronto:</b> {time_casa} <b>vs</b> {time_fora}\n\n"
    
    return msg


def _format_tactical_script(master_analysis: Dict, time_casa: str, time_fora: str) -> str:
    """Formata seção de Roteiro Tático."""
    analysis_summary = master_analysis.get('analysis_summary', {})
    script_name = analysis_summary.get('selected_script', 'SCRIPT_BALANCED_GAME')
    reasoning = analysis_summary.get('reasoning', 'Análise em andamento')
    
    # Limpar nome do script para exibição
    script_display = script_name.replace('SCRIPT_', '').replace('_', ' ').title()
    
    msg = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📖 <b>ROTEIRO TÁTICO</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"🎬 <b>Script:</b> {script_display}\n\n"
    msg += f"💭 <b>Raciocínio:</b>\n{reasoning}\n\n"
    
    return msg


def _format_analise_principal(
    palpite: Dict,
    stats_casa: Dict,
    stats_fora: Dict,
    time_casa: str,
    time_fora: str,
    master_analysis: Dict,
    ultimos_jogos_casa: Optional[List[Dict]],
    ultimos_jogos_fora: Optional[List[Dict]]
) -> str:
    """Formata ANÁLISE PRINCIPAL (com ou sem odd)."""
    tem_odd = palpite.get('odd') is not None and palpite.get('odd') > 0
    confianca = palpite.get('confianca', 0)
    
    # Título dinâmico baseado em presença de odd
    if tem_odd:
        titulo = "💎 <b>ANÁLISE PRINCIPAL</b>"
    else:
        titulo = "💎 <b>ANÁLISE PRINCIPAL (OPORTUNIDADE TÁTICA)</b>"
    
    msg = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"{titulo}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Nome do palpite
    nome_palpite = _format_bet_name(palpite)
    msg += f"🎯 <b>Mercado:</b> {nome_palpite}\n"
    
    if tem_odd:
        msg += f"📊 <b>Odd:</b> @{palpite['odd']}\n"
    else:
        msg += f"⚠️ <b>Odd:</b> Não disponível no mercado (análise estatística pura)\n"
    
    msg += f"💎 <b>Confiança:</b> {confianca:.1f}/10\n\n"
    
    # Justificativa
    msg += f"📖 <b>JUSTIFICATIVA:</b>\n"
    justificativa = _generate_justification(palpite, stats_casa, stats_fora, time_casa, time_fora, master_analysis)
    msg += justificativa + "\n\n"
    
    # Evidências
    msg += f"📊 <b>EVIDÊNCIAS:</b>\n"
    evidencias = _generate_evidence(palpite, stats_casa, stats_fora, time_casa, time_fora, ultimos_jogos_casa, ultimos_jogos_fora, master_analysis)
    msg += evidencias + "\n\n"
    
    return msg


def _format_sugestoes_taticas(sugestoes: List[Dict]) -> str:
    """Formata seção de SUGESTÕES TÁTICAS (sem odd)."""
    msg = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🧠 <b>SUGESTÕES TÁTICAS</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"<i>Análises de alto valor sem odd disponível no mercado:</i>\n\n"
    
    for idx, palpite in enumerate(sugestoes[:3], 1):  # Máximo 3
        nome = _format_bet_name(palpite)
        conf = palpite.get('confianca', 0)
        msg += f"{idx}. <b>{nome}</b>\n"
        msg += f"   Confiança: {conf:.1f}/10\n\n"
    
    return msg


def _format_palpites_alternativos(palpites: List[Dict]) -> str:
    """Formata seção de PALPITES ALTERNATIVOS (com odd)."""
    msg = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎯 <b>PALPITES ALTERNATIVOS</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for idx, palpite in enumerate(palpites[:5], 1):  # Máximo 5
        nome = _format_bet_name(palpite)
        odd = palpite.get('odd', 0)
        conf = palpite.get('confianca', 0)
        msg += f"{idx}. <b>{nome}</b> @{odd} - Conf: {conf:.1f}/10\n"
    
    msg += "\n"
    return msg


def _format_bet_name(palpite: Dict) -> str:
    """Formata nome completo de um palpite."""
    mercado = palpite.get('mercado', 'Gols')
    tipo = palpite.get('tipo', '')
    time_tipo = palpite.get('time', '')
    periodo = palpite.get('periodo', 'FT')
    
    nome = f"{tipo} {mercado}"
    if time_tipo and time_tipo != 'Total':
        nome += f" ({time_tipo})"
    if periodo != 'FT':
        nome += f" {periodo}"
    
    return nome


def _generate_justification(
    palpite: Dict,
    stats_casa: Dict,
    stats_fora: Dict,
    time_casa: str,
    time_fora: str,
    master_analysis: Dict
) -> str:
    """Gera justificativa dinâmica baseada em dados reais."""
    mercado = palpite.get('mercado', 'Gols')
    tipo = palpite.get('tipo', '')
    
    # Extrair dados
    gols_casa = stats_casa.get('casa', {}).get('gols_marcados', 0)
    gols_fora = stats_fora.get('fora', {}).get('gols_marcados', 0)
    gols_casa_sofridos = stats_casa.get('casa', {}).get('gols_sofridos', 0)
    gols_fora_sofridos = stats_fora.get('fora', {}).get('gols_sofridos', 0)
    
    if mercado == 'Gols' and 'Over' in tipo:
        media_total = (gols_casa + gols_fora_sofridos + gols_fora + gols_casa_sofridos) / 2
        justificativa = (
            f"{time_casa} marca <b>{gols_casa:.1f} gols</b> em casa, "
            f"enquanto {time_fora} marca <b>{gols_fora:.1f} gols</b> fora. "
            f"Média combinada de <b>{media_total:.1f} gols</b> favorece {tipo}."
        )
    
    elif mercado == 'Gols' and 'Under' in tipo:
        justificativa = (
            f"Perfil defensivo: {time_casa} marca apenas <b>{gols_casa:.1f} gols</b> em casa, "
            f"{time_fora} marca <b>{gols_fora:.1f} gols</b> fora. Jogo travado esperado."
        )
    
    elif mercado == 'Cantos':
        cantos_casa = stats_casa.get('casa', {}).get('cantos_feitos', 0)
        cantos_fora = stats_fora.get('fora', {}).get('cantos_feitos', 0)
        justificativa = (
            f"{time_casa} força <b>{cantos_casa:.1f} escanteios</b> em casa, "
            f"{time_fora} força <b>{cantos_fora:.1f} escanteios</b> fora. "
            f"Volume ofensivo favorece {tipo}."
        )
    
    elif mercado == 'BTTS':
        justificativa = (
            f"Análise de gols marcados e sofridos indica {'ambos marcarem' if tipo == 'Sim' else 'pelo menos um time não marcar'}. "
            f"Casa: {gols_casa:.1f} gols marcados. Fora: {gols_fora:.1f} gols marcados."
        )
    
    else:
        justificativa = f"Análise técnica favorece {tipo} {mercado} baseado nas métricas ponderadas."
    
    # Adicionar contexto do script tático
    script_name = master_analysis.get('analysis_summary', {}).get('selected_script', '')
    if script_name:
        script_display = script_name.replace('SCRIPT_', '').replace('_', ' ').title()
        justificativa += f"\n\n🧠 <b>Contexto Tático:</b> {script_display}"
    
    return justificativa


def _generate_evidence(
    palpite: Dict,
    stats_casa: Dict,
    stats_fora: Dict,
    time_casa: str,
    time_fora: str,
    ultimos_jogos_casa: Optional[List[Dict]],
    ultimos_jogos_fora: Optional[List[Dict]],
    master_analysis: Dict
) -> str:
    """Gera evidências estatísticas (preferencialmente weighted metrics)."""
    mercado = palpite.get('mercado', 'Gols')
    evidencias = ""
    
    # Tentar usar weighted metrics se disponível
    weighted_home = master_analysis.get('analysis_summary', {}).get('weighted_metrics_home', {})
    weighted_away = master_analysis.get('analysis_summary', {}).get('weighted_metrics_away', {})
    use_weighted = bool(weighted_home and weighted_away)
    
    if mercado == 'Gols':
        if ultimos_jogos_casa and len(ultimos_jogos_casa) > 0:
            evidencias += f"<b>Últimos 4 jogos - {time_casa}:</b>\n"
            for idx, jogo in enumerate(ultimos_jogos_casa[:4], 1):
                gols = jogo.get('goals_total', 0)
                evidencias += f"  {idx}. {gols} gols\n"
        else:
            media_casa = stats_casa.get('casa', {}).get('gols_marcados', 0)
            evidencias += f"<b>{time_casa}:</b> Média {media_casa:.1f} gols/jogo\n"
        
        if ultimos_jogos_fora and len(ultimos_jogos_fora) > 0:
            evidencias += f"\n<b>Últimos 4 jogos - {time_fora}:</b>\n"
            for idx, jogo in enumerate(ultimos_jogos_fora[:4], 1):
                gols = jogo.get('goals_total', 0)
                evidencias += f"  {idx}. {gols} gols\n"
        else:
            media_fora = stats_fora.get('fora', {}).get('gols_marcados', 0)
            evidencias += f"<b>{time_fora}:</b> Média {media_fora:.1f} gols/jogo\n"
    
    elif mercado == 'Cantos':
        if use_weighted:
            cantos_casa_weighted = weighted_home.get('weighted_corners_for', 0)
            cantos_fora_weighted = weighted_away.get('weighted_corners_for', 0)
            evidencias += f"<b>Cantos Ponderados por SoS:</b>\n"
            evidencias += f"  {time_casa}: {cantos_casa_weighted:.1f} cantos/jogo\n"
            evidencias += f"  {time_fora}: {cantos_fora_weighted:.1f} cantos/jogo\n"
            evidencias += f"  Média combinada: {(cantos_casa_weighted + cantos_fora_weighted):.1f}\n"
        else:
            cantos_casa = stats_casa.get('casa', {}).get('cantos_feitos', 0)
            cantos_fora = stats_fora.get('fora', {}).get('cantos_feitos', 0)
            evidencias += f"<b>Cantos:</b>\n"
            evidencias += f"  {time_casa}: {cantos_casa:.1f} cantos/jogo\n"
            evidencias += f"  {time_fora}: {cantos_fora:.1f} cantos/jogo\n"
    
    elif mercado == 'Cartões':
        cartoes_casa = stats_casa.get('casa', {}).get('cartoes_amarelos', 0) + stats_casa.get('casa', {}).get('cartoes_vermelhos', 0)
        cartoes_fora = stats_fora.get('fora', {}).get('cartoes_amarelos', 0) + stats_fora.get('fora', {}).get('cartoes_vermelhos', 0)
        evidencias += f"<b>Cartões:</b>\n"
        evidencias += f"  {time_casa}: {cartoes_casa:.1f} cartões/jogo\n"
        evidencias += f"  {time_fora}: {cartoes_fora:.1f} cartões/jogo\n"
    
    # Adicionar QSC se disponível
    qsc_home = master_analysis.get('analysis_summary', {}).get('qsc_home')
    qsc_away = master_analysis.get('analysis_summary', {}).get('qsc_away')
    if qsc_home and qsc_away:
        evidencias += f"\n<b>Quality Score (QSC):</b>\n"
        evidencias += f"  {time_casa}: {qsc_home:.0f}\n"
        evidencias += f"  {time_fora}: {qsc_away:.0f}\n"
    
    return evidencias


# Manter compatibilidade com código existente
def format_dossier_message(*args, **kwargs):
    """Wrapper para compatibilidade. Use format_phoenix_dossier diretamente."""
    return format_phoenix_dossier(*args, **kwargs)
