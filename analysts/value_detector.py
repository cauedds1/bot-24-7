# analysts/value_detector.py
"""
Módulo de detecção de valor matemático e contextual em apostas esportivas.
Calcula Expected Value (EV) e identifica apostas de valor positivo.
"""

def calculate_value_score(bot_probability, market_odds):
    """
    Calcula o Value Score matemático de uma aposta.
    
    Args:
        bot_probability (float): Probabilidade estimada pelo bot (0.0 a 1.0)
        market_odds (float): Odd oferecida pelo mercado
    
    Returns:
        float: Value Score (diferença entre prob. bot e prob. implícita)
               Positivo = valor encontrado, Negativo = sem valor
    
    Example:
        >>> calculate_value_score(0.65, 1.80)
        0.0944  # +9.44% de valor
    """
    # Converter odd para float (pode vir como string da API)
    try:
        market_odds = float(market_odds)
    except (ValueError, TypeError):
        return 0.0
    
    if market_odds <= 1.0:
        return 0.0
    
    # Probabilidade implícita da odd do mercado
    implied_probability = 1.0 / market_odds
    
    # Value Score = diferença entre nossa estimativa e a do mercado
    value_score = bot_probability - implied_probability
    
    return value_score


def format_value_percentage(value_score):
    """
    Formata Value Score como percentual com sinal.
    
    Args:
        value_score (float): Value Score calculado
    
    Returns:
        str: Percentual formatado (ex: "+9.4%" ou "-3.2%")
    """
    percentage = value_score * 100
    sign = '+' if percentage >= 0 else ''
    return f"{sign}{percentage:.1f}%"


def get_value_rating(value_score):
    """
    Converte Value Score em rating qualitativo.
    
    Args:
        value_score (float): Value Score calculado
    
    Returns:
        tuple: (rating, emoji)
    
    Example:
        >>> get_value_rating(0.15)
        ('EXCELENTE', '💎')
    """
    if value_score >= 0.15:
        return ('EXCELENTE', '💎')
    elif value_score >= 0.10:
        return ('MUITO BOM', '🔥')
    elif value_score >= 0.05:
        return ('BOM', '✅')
    elif value_score >= 0.02:
        return ('RAZOÁVEL', '⚡')
    elif value_score >= 0.0:
        return ('MARGINAL', '⚠️')
    else:
        return ('SEM VALOR', '❌')


def detectar_valor_contextual(stats_casa, stats_fora, jogo_info=None, classificacao=None):
    """
    Identifica contextos que tornam odds "baixas" (1.50-2.50) valiosas:
    - Favorito muito forte (diferença de força >= 2.0)
    - Clássico/Derby (rivalidade alta)
    - Jogo decisivo (top 4 vs top 4, ou luta contra rebaixamento)
    - Necessidade de resultado (time precisa vencer para classificar)
    """
    contextos_valor = {
        'favorito_forte': False,
        'classico_derby': False,
        'jogo_decisivo': False,
        'necessidade_resultado': False,
        'jogo_tenso': False
    }

    # 1. FAVORITO MUITO FORTE
    forca_casa = stats_casa['casa'].get('gols_marcados', 0) - stats_casa['casa'].get('gols_sofridos', 0)
    forca_fora = stats_fora['fora'].get('gols_marcados', 0) - stats_fora['fora'].get('gols_sofridos', 0)
    diferenca_forca = abs(forca_casa - forca_fora)

    if diferenca_forca >= 2.0:
        contextos_valor['favorito_forte'] = True

    # 2. CLÁSSICO/DERBY (times tradicionais)
    if jogo_info:
        time_casa = jogo_info.get('teams', {}).get('home', {}).get('name', '').lower()
        time_fora = jogo_info.get('teams', {}).get('away', {}).get('name', '').lower()

        # Times brasileiros tradicionais
        times_grandes_br = ['palmeiras', 'flamengo', 'corinthians', 'são paulo', 'santos', 
                            'grêmio', 'internacional', 'atlético', 'cruzeiro', 'botafogo']

        # Clássicos conhecidos
        classicos = [
            ('palmeiras', 'corinthians'),  # Dérbi
            ('flamengo', 'vasco'),  # Clássico dos Milhões
            ('flamengo', 'fluminense'),  # Fla-Flu
            ('são paulo', 'corinthians'),  # Majestoso
            ('grêmio', 'internacional'),  # Grenal
            ('atlético', 'cruzeiro'),  # Clássico Mineiro
        ]

        # Verificar se é clássico
        for t1, t2 in classicos:
            if (t1 in time_casa and t2 in time_fora) or (t2 in time_casa and t1 in time_fora):
                contextos_valor['classico_derby'] = True
                contextos_valor['jogo_tenso'] = True
                break

        # Verificar se são dois times grandes (mesmo sem ser clássico tradicional)
        casa_grande = any(t in time_casa for t in times_grandes_br)
        fora_grande = any(t in time_fora for t in times_grandes_br)
        if casa_grande and fora_grande:
            contextos_valor['jogo_tenso'] = True

    # 3. JOGO DECISIVO (baseado em posição na tabela)
    if classificacao:
        try:
            pos_casa = None
            pos_fora = None

            if jogo_info:
                time_casa_nome = jogo_info.get('teams', {}).get('home', {}).get('name', '')
                time_fora_nome = jogo_info.get('teams', {}).get('away', {}).get('name', '')

                for time in classificacao:
                    if time['team']['name'] == time_casa_nome:
                        pos_casa = time['rank']
                    if time['team']['name'] == time_fora_nome:
                        pos_fora = time['rank']

            # Top 4 vs Top 4 = Jogo decisivo
            if pos_casa and pos_fora and pos_casa <= 4 and pos_fora <= 4:
                contextos_valor['jogo_decisivo'] = True
                contextos_valor['necessidade_resultado'] = True

            # Zona de rebaixamento vs Zona de rebaixamento = Jogo decisivo
            if pos_casa and pos_fora and pos_casa >= 16 and pos_fora >= 16:
                contextos_valor['jogo_decisivo'] = True
                contextos_valor['necessidade_resultado'] = True
        except Exception as e:
            # Erro ao processar posições da tabela não é crítico
            pass

    return contextos_valor

def ajustar_odd_minima_por_contexto(odd_base, contextos_valor, mercado='gols'):
    """
    Ajusta a odd mínima aceita baseado no contexto.
    Permite odds menores quando há VALOR CONTEXTUAL.

    Args:
        odd_base: Odd original (ex: 1.50)
        contextos_valor: Dict retornado por detectar_valor_contextual()
        mercado: Tipo de mercado ('gols', 'cartoes', 'cantos', etc)

    Returns:
        True se a odd tem valor contextual, False caso contrário
    """
    # FAVORITO FORTE: aceitar odds 1.50+ para vitória
    if contextos_valor['favorito_forte'] and mercado in ['resultado', 'gols', 'handicap']:
        if odd_base >= 1.50:
            return True

    # CLÁSSICO/DERBY: aceitar odds 1.70+ para cartões
    if contextos_valor['classico_derby'] and mercado == 'cartoes':
        if odd_base >= 1.70:
            return True

    # JOGO TENSO: aceitar odds 1.75+ para over gols/cartões
    if contextos_valor['jogo_tenso'] and mercado in ['gols', 'cartoes']:
        if odd_base >= 1.75:
            return True

    # NECESSIDADE DE RESULTADO: aceitar odds 1.80+ para cantos
    if contextos_valor['necessidade_resultado'] and mercado == 'cantos':
        if odd_base >= 1.80:
            return True

    # JOGO DECISIVO: aceitar odds 1.85+ para qualquer mercado
    if contextos_valor['jogo_decisivo']:
        if odd_base >= 1.85:
            return True

    return False
