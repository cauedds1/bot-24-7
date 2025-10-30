# analysts/justification_generator.py
"""
Gerador de justificativas persuasivas e dinâmicas para apostas esportivas.
Explica o "porquê" de cada sugestão de forma convincente e não-genérica.
"""

def generate_persuasive_justification(mercado, tipo, value_score, game_script=None, expectativa_gols=None, 
                                       quality_home=None, quality_away=None, odd=None, **kwargs):
    """
    Gera justificativa persuasiva e dinâmica para uma sugestão de aposta.
    
    Args:
        mercado (str): Tipo de mercado ('Gols', 'Cantos', 'Cartões', etc.)
        tipo (str): Tipo específico ('Over 2.5', 'BTTS Sim', etc.)
        value_score (float): Value Score calculado
        game_script (str): Roteiro do jogo (DOMINIO_CASA, EQUILIBRADO, etc.)
        expectativa_gols (float): Expectativa total de gols
        quality_home (int): Qualidade técnica do time da casa
        quality_away (int): Qualidade técnica do time visitante
        odd (float): Odd da aposta
        **kwargs: Outros dados contextuais
    
    Returns:
        str: Justificativa persuasiva formatada
    """
    
    # --- MERCADO DE GOLS ---
    if mercado == "Gols":
        return _justificar_gols(tipo, value_score, game_script, expectativa_gols, 
                                quality_home, quality_away, odd, **kwargs)
    
    # --- MERCADO DE CANTOS ---
    elif mercado == "Cantos":
        return _justificar_cantos(tipo, value_score, game_script, **kwargs)
    
    # --- MERCADO DE CARTÕES ---
    elif mercado == "Cartões":
        return _justificar_cartoes(tipo, value_score, game_script, **kwargs)
    
    # --- MERCADO BTTS ---
    elif mercado == "BTTS":
        return _justificar_btts(tipo, value_score, expectativa_gols, **kwargs)
    
    # --- FALLBACK GENÉRICO ---
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_gols(tipo, value_score, game_script, expectativa_gols, quality_home, quality_away, odd, **kwargs):
    """Justificativa específica para mercado de Gols"""
    
    # Calcular diferença de qualidade
    quality_diff = abs(quality_home - quality_away) if quality_home and quality_away else 0
    value_pct = f"{value_score*100:+.1f}%"
    
    # --- CENÁRIO 1: DOMÍNIO TÉCNICO + OVER ---
    if game_script and "DOMINIO" in game_script and "Over" in tipo:
        time_dominante = "casa" if "CASA" in game_script else "visitante"
        qual_forte = quality_home if "CASA" in game_script else quality_away
        qual_fraco = quality_away if "CASA" in game_script else quality_home
        
        justificativa = (
            f"📊 <b>Análise Técnica:</b> Domínio claro do time <b>{time_dominante}</b> "
            f"(Qualidade <b>{qual_forte}</b> vs <b>{qual_fraco}</b>). "
        )
        
        if expectativa_gols:
            justificativa += f"Nossa projeção indica <b>{expectativa_gols:.1f} gols</b> no jogo. "
        
        justificativa += (
            f"\n\n💡 <b>Oportunidade de Valor:</b> A odd de <b>@{odd:.2f}</b> para {tipo} "
            f"implica uma probabilidade menor do que nossa análise sugere, "
            f"gerando um valor positivo de <b>{value_pct}</b>."
        )
        
        return justificativa
    
    # --- CENÁRIO 2: FAVORITISMO + OVER ---
    elif game_script and "FAVORITISMO" in game_script and "Over" in tipo:
        time_favorito = "casa" if "CASA" in game_script else "visitante"
        
        justificativa = (
            f"📊 <b>Análise Técnica:</b> Favoritismo moderado do time <b>{time_favorito}</b> "
            f"(Diferença de qualidade: <b>{quality_diff} pontos</b>). "
        )
        
        if expectativa_gols:
            justificativa += f"Expectativa de <b>{expectativa_gols:.1f} gols</b> baseada no confronto ofensivo/defensivo. "
        
        justificativa += (
            f"\n\n💰 <b>Valor Matemático:</b> O mercado subprecificou esta linha. "
            f"A odd @{odd:.2f} oferece <b>{value_pct}</b> de valor sobre nossa estimativa."
        )
        
        return justificativa
    
    # --- CENÁRIO 3: EQUILIBRADO + OVER (Baseado em Estatísticas) ---
    elif game_script == "EQUILIBRADO" and "Over" in tipo and expectativa_gols:
        justificativa = (
            f"⚖️ <b>Jogo Equilibrado:</b> Sem disparidade técnica clara "
            f"(Qualidade: <b>{quality_home}</b> vs <b>{quality_away}</b>). "
            f"A análise se baseia no confronto estatístico entre <b>ataque e defesa</b>.\n\n"
        )
        
        justificativa += (
            f"📈 <b>Projeção:</b> Com <b>{expectativa_gols:.1f} gols</b> esperados, "
            f"a linha {tipo} a <b>@{odd:.2f}</b> apresenta valor matemático interessante. "
            f"O mercado parece ter subestimado o potencial ofensivo (<b>{value_pct}</b> de valor)."
        )
        
        return justificativa
    
    # --- CENÁRIO 4: EQUILIBRADO + UNDER (Defesas Fortes) ---
    elif game_script == "EQUILIBRADO" and "Under" in tipo and expectativa_gols:
        justificativa = (
            f"🛡️ <b>Confronto Equilibrado:</b> O ponto-chave é a <b>força defensiva</b> de ambas as equipes. "
            f"Com expectativa de apenas <b>{expectativa_gols:.1f} gols</b>, "
            f"a linha {tipo} a <b>@{odd:.2f}</b> tem valor matemático.\n\n"
        )
        
        justificativa += (
            f"💡 <b>Insight:</b> O mercado parece superestimar o potencial ofensivo desta partida. "
            f"Nossa análise identifica <b>{value_pct}</b> de valor positivo nesta aposta."
        )
        
        return justificativa
    
    # --- CENÁRIO 5: FALLBACK COM EXPECTATIVA ---
    elif expectativa_gols:
        over_under = "Over" if "Over" in tipo else "Under"
        trend = "ofensiva" if over_under == "Over" else "defensiva"
        
        justificativa = (
            f"📊 <b>Análise Estatística:</b> Expectativa de <b>{expectativa_gols:.1f} gols</b> "
            f"baseada no histórico recente e tendência <b>{trend}</b> das equipes.\n\n"
        )
        
        justificativa += (
            f"💰 <b>Valor Identificado:</b> A odd @{odd:.2f} oferece <b>{value_pct}</b> "
            f"de valor sobre nossa projeção matemática."
        )
        
        return justificativa
    
    # --- FALLBACK GENÉRICO ---
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_cantos(tipo, value_score, game_script, **kwargs):
    """Justificativa específica para mercado de Cantos"""
    
    projecao_cantos = kwargs.get('projecao_cantos')
    estilo_jogo = kwargs.get('estilo_jogo', 'padrão')
    odd = kwargs.get('odd', 0)
    value_pct = f"{value_score*100:+.1f}%"
    
    if game_script and "DOMINIO" in game_script:
        time_dominante = "casa" if "CASA" in game_script else "visitante"
        
        justificativa = (
            f"🚩 <b>Domínio Técnico:</b> O time <b>{time_dominante}</b> tende a dominar a posse "
            f"e pressionar constantemente, gerando <b>muitas finalizações e escanteios</b>.\n\n"
        )
        
        if projecao_cantos:
            justificativa += f"📈 Nossa projeção: <b>{projecao_cantos:.1f} cantos</b>. "
        
        justificativa += (
            f"A odd @{odd:.2f} para {tipo} oferece <b>{value_pct}</b> "
            f"de valor, pois o mercado subestimou o volume de ataques esperado."
        )
        
        return justificativa
    
    elif estilo_jogo == "vertical" or estilo_jogo == "ataque_contra_ataque":
        justificativa = (
            f"⚡ <b>Estilo de Jogo:</b> Partida com estilo <b>{estilo_jogo.replace('_', ' ')}</b>, "
            f"favorecendo transições rápidas e muitas finalizações.\n\n"
        )
        
        if projecao_cantos:
            justificativa += f"Nossa projeção de <b>{projecao_cantos:.1f} cantos</b> "
        
        justificativa += (
            f"sugere que {tipo} a <b>@{odd:.2f}</b> está mal precificado "
            f"(<b>{value_pct}</b> de valor positivo)."
        )
        
        return justificativa
    
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_cartoes(tipo, value_score, game_script, **kwargs):
    """Justificativa específica para mercado de Cartões"""
    
    intensidade = kwargs.get('intensidade', 'média')
    classico = kwargs.get('classico', False)
    odd = kwargs.get('odd', 0)
    value_pct = f"{value_score*100:+.1f}%"
    
    if classico:
        justificativa = (
            f"🔥 <b>Clássico/Derby:</b> Rivalidade histórica eleva a <b>intensidade emocional</b> "
            f"do confronto. Estatisticamente, clássicos têm <b>50% mais cartões</b> que jogos normais.\n\n"
        )
        
        justificativa += (
            f"💡 A linha {tipo} a <b>@{odd:.2f}</b> não precificou adequadamente este fator, "
            f"gerando <b>{value_pct}</b> de valor."
        )
        
        return justificativa
    
    elif intensidade == "alta":
        justificativa = (
            f"⚠️ <b>Jogo de Alta Intensidade:</b> Ambas as equipes têm estilo físico e histórico "
            f"de muitas faltas. Expectativa de <b>arbitragem rigorosa</b>.\n\n"
        )
        
        justificativa += (
            f"📊 Nossa análise indica que {tipo} a <b>@{odd:.2f}</b> "
            f"oferece <b>{value_pct}</b> de valor matemático."
        )
        
        return justificativa
    
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_btts(tipo, value_score, expectativa_gols, **kwargs):
    """Justificativa específica para mercado BTTS"""
    
    odd = kwargs.get('odd', 0)
    value_pct = f"{value_score*100:+.1f}%"
    defesas_fracas = kwargs.get('defesas_fracas', False)
    
    if "Sim" in tipo and defesas_fracas:
        justificativa = (
            f"🎯 <b>Defesas Vulneráveis:</b> Ambos os times têm <b>defesas frágeis</b> "
            f"e concedem gols regularmente em casa/fora.\n\n"
        )
        
        if expectativa_gols:
            justificativa += f"Com expectativa de <b>{expectativa_gols:.1f} gols</b>, "
        
        justificativa += (
            f"BTTS Sim a <b>@{odd:.2f}</b> oferece <b>{value_pct}</b> "
            f"de valor, já que ambos têm alto poder ofensivo."
        )
        
        return justificativa
    
    elif "Não" in tipo:
        justificativa = (
            f"🛡️ <b>Solidez Defensiva:</b> Pelo menos um dos times possui <b>defesa consistente</b>, "
            f"reduzindo a probabilidade de ambos marcarem.\n\n"
        )
        
        justificativa += (
            f"💰 A odd @{odd:.2f} para BTTS Não está subvalorizada, "
            f"oferecendo <b>{value_pct}</b> de valor matemático."
        )
        
        return justificativa
    
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_generica(tipo, value_score, odd):
    """Justificativa genérica de fallback"""
    
    value_pct = f"{value_score*100:+.1f}%"
    
    if value_score >= 0.10:
        intensidade = "excelente"
    elif value_score >= 0.05:
        intensidade = "boa"
    else:
        intensidade = "razoável"
    
    justificativa = (
        f"📊 <b>Análise Matemática:</b> Nossa avaliação técnica identificou "
        f"uma <b>{intensidade} oportunidade de valor</b> nesta linha.\n\n"
    )
    
    justificativa += (
        f"💰 A odd @{odd:.2f} para {tipo} oferece <b>{value_pct}</b> "
        f"de valor positivo sobre nossa estimativa de probabilidade."
    )
    
    return justificativa
