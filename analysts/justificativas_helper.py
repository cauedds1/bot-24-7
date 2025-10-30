# analysts/justificativas_helper.py
from api_client import buscar_ultimos_jogos_time, buscar_estatisticas_jogo

def gerar_justificativa_ultimos_jogos(time_id_casa, time_id_fora, mercado_tipo, resultado):
    """
    Gera justificativa detalhada com dados reais dos últimos 4 jogos.
    
    Args:
        time_id_casa: ID do time da casa
        time_id_fora: ID do time de fora
        mercado_tipo: Tipo do mercado ('cantos', 'cartoes', 'chutes', 'gols')
        resultado: Dict com informações do palpite (tipo, linha, time_alvo)
    
    Returns:
        String formatada com dados dos últimos 4 jogos e conclusão convincente
    """
    
    # Buscar últimos 4 jogos de cada time
    jogos_casa = buscar_ultimos_jogos_time(time_id_casa, limite=4) or []
    jogos_fora = buscar_ultimos_jogos_time(time_id_fora, limite=4) or []
    
    if not jogos_casa and not jogos_fora:
        return "📖 JUSTIFICATIVA:\n✅ CONCLUSÃO: Estatísticas MUITO FAVORÁVEIS. Os dados indicam alta probabilidade de acerto."
    
    # Processar dados conforme o mercado
    if mercado_tipo == 'cantos':
        return _formatar_justificativa_cantos(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado)
    elif mercado_tipo == 'cartoes':
        return _formatar_justificativa_cartoes(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado)
    elif mercado_tipo == 'chutes':
        return _formatar_justificativa_chutes(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado)
    elif mercado_tipo == 'gols':
        return _formatar_justificativa_gols(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado)
    
    return "📖 JUSTIFICATIVA:\n✅ CONCLUSÃO: Estatísticas MUITO FAVORÁVEIS. Os dados indicam alta probabilidade de acerto."


def _extrair_stats_jogo(jogo, time_id, stat_name):
    """Extrai estatística específica de um jogo."""
    if not jogo:
        return None
    
    fixture_id = jogo.get('fixture_id')
    teams_info = jogo.get('teams', {})
    
    # Determinar se o time jogou em casa ou fora
    home_id = teams_info.get('home', {}).get('id')
    away_id = teams_info.get('away', {}).get('id')
    
    if home_id != time_id and away_id != time_id:
        return None
    
    team_key = 'home' if home_id == time_id else 'away'
    opponent_key = 'away' if home_id == time_id else 'home'
    
    # Buscar estatísticas do jogo
    stats = jogo.get('statistics')
    if not stats:
        stats = buscar_estatisticas_jogo(fixture_id)
        if not stats:
            return None
    
    # Extrair estatística específica
    valor_time = stats.get(team_key, {}).get(stat_name, 0) or 0
    valor_oponente = stats.get(opponent_key, {}).get(stat_name, 0) or 0
    
    return {
        'time': int(valor_time) if valor_time else 0,
        'oponente': int(valor_oponente) if valor_oponente else 0,
        'total': int(valor_time) + int(valor_oponente) if valor_time and valor_oponente else 0,
        'adversario': teams_info.get(opponent_key, {}).get('name', 'N/A')
    }


def _formatar_justificativa_cantos(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado):
    """Formata justificativa específica para mercado de cantos."""
    
    # Extrair dados de cantos dos últimos 4 jogos
    cantos_casa_historico = []
    for jogo in jogos_casa[:4]:
        dados = _extrair_stats_jogo(jogo, time_id_casa, 'Corner Kicks')
        if dados:
            cantos_casa_historico.append(dados)
    
    cantos_fora_historico = []
    for jogo in jogos_fora[:4]:
        dados = _extrair_stats_jogo(jogo, time_id_fora, 'Corner Kicks')
        if dados:
            cantos_fora_historico.append(dados)
    
    if not cantos_casa_historico and not cantos_fora_historico:
        return "📖 JUSTIFICATIVA:\n✅ CONCLUSÃO: Estatísticas favoráveis para este mercado."
    
    # Formatar dados dos jogos
    texto = "📖 JUSTIFICATIVA:\n\n"
    texto += "📊 <b>ÚLTIMOS 4 JOGOS - ESCANTEIOS:</b>\n\n"
    
    if cantos_casa_historico:
        nome_casa = jogos_casa[0].get('teams', {}).get('home' if jogos_casa[0].get('teams', {}).get('home', {}).get('id') == time_id_casa else 'away', {}).get('name', 'Casa')
        texto += f"🏠 <b>{nome_casa}:</b>\n"
        for i, dados in enumerate(cantos_casa_historico, 1):
            texto += f"   {i}. {dados['time']} escanteios (vs {dados['adversario'][:20]})\n"
        
        media_casa = sum(d['time'] for d in cantos_casa_historico) / len(cantos_casa_historico)
        texto += f"   <b>Média:</b> {media_casa:.1f} escanteios/jogo\n\n"
    
    if cantos_fora_historico:
        nome_fora = jogos_fora[0].get('teams', {}).get('home' if jogos_fora[0].get('teams', {}).get('home', {}).get('id') == time_id_fora else 'away', {}).get('name', 'Fora')
        texto += f"✈️ <b>{nome_fora}:</b>\n"
        for i, dados in enumerate(cantos_fora_historico, 1):
            texto += f"   {i}. {dados['time']} escanteios (vs {dados['adversario'][:20]})\n"
        
        media_fora = sum(d['time'] for d in cantos_fora_historico) / len(cantos_fora_historico)
        texto += f"   <b>Média:</b> {media_fora:.1f} escanteios/jogo\n\n"
    
    # Gerar conclusão convincente baseada nos dados
    texto += _gerar_conclusao_cantos(cantos_casa_historico, cantos_fora_historico, resultado)
    
    return texto


def _formatar_justificativa_cartoes(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado):
    """Formata justificativa específica para mercado de cartões."""
    
    # Extrair dados de cartões dos últimos 4 jogos
    cartoes_casa_historico = []
    for jogo in jogos_casa[:4]:
        amarelos = _extrair_stats_jogo(jogo, time_id_casa, 'Yellow Cards')
        vermelhos = _extrair_stats_jogo(jogo, time_id_casa, 'Red Cards')
        if amarelos and vermelhos:
            total_cartoes = amarelos['time'] + vermelhos['time']
            cartoes_casa_historico.append({
                'total': total_cartoes,
                'amarelos': amarelos['time'],
                'vermelhos': vermelhos['time'],
                'adversario': amarelos['adversario']
            })
    
    cartoes_fora_historico = []
    for jogo in jogos_fora[:4]:
        amarelos = _extrair_stats_jogo(jogo, time_id_fora, 'Yellow Cards')
        vermelhos = _extrair_stats_jogo(jogo, time_id_fora, 'Red Cards')
        if amarelos and vermelhos:
            total_cartoes = amarelos['time'] + vermelhos['time']
            cartoes_fora_historico.append({
                'total': total_cartoes,
                'amarelos': amarelos['time'],
                'vermelhos': vermelhos['time'],
                'adversario': amarelos['adversario']
            })
    
    if not cartoes_casa_historico and not cartoes_fora_historico:
        return "📖 JUSTIFICATIVA:\n✅ CONCLUSÃO: Estatísticas favoráveis para este mercado."
    
    # Formatar dados dos jogos
    texto = "📖 JUSTIFICATIVA:\n\n"
    texto += "📊 <b>ÚLTIMOS 4 JOGOS - CARTÕES:</b>\n\n"
    
    if cartoes_casa_historico:
        nome_casa = jogos_casa[0].get('teams', {}).get('home' if jogos_casa[0].get('teams', {}).get('home', {}).get('id') == time_id_casa else 'away', {}).get('name', 'Casa')
        texto += f"🏠 <b>{nome_casa}:</b>\n"
        for i, dados in enumerate(cartoes_casa_historico, 1):
            texto += f"   {i}. {dados['total']} cartões ({dados['amarelos']}🟨 {dados['vermelhos']}🟥) vs {dados['adversario'][:20]}\n"
        
        media_casa = sum(d['total'] for d in cartoes_casa_historico) / len(cartoes_casa_historico)
        texto += f"   <b>Média:</b> {media_casa:.1f} cartões/jogo\n\n"
    
    if cartoes_fora_historico:
        nome_fora = jogos_fora[0].get('teams', {}).get('home' if jogos_fora[0].get('teams', {}).get('home', {}).get('id') == time_id_fora else 'away', {}).get('name', 'Fora')
        texto += f"✈️ <b>{nome_fora}:</b>\n"
        for i, dados in enumerate(cartoes_fora_historico, 1):
            texto += f"   {i}. {dados['total']} cartões ({dados['amarelos']}🟨 {dados['vermelhos']}🟥) vs {dados['adversario'][:20]}\n"
        
        media_fora = sum(d['total'] for d in cartoes_fora_historico) / len(cartoes_fora_historico)
        texto += f"   <b>Média:</b> {media_fora:.1f} cartões/jogo\n\n"
    
    # Gerar conclusão convincente baseada nos dados
    texto += _gerar_conclusao_cartoes(cartoes_casa_historico, cartoes_fora_historico, resultado)
    
    return texto


def _formatar_justificativa_chutes(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado):
    """Formata justificativa específica para mercado de finalizações."""
    
    # Extrair dados de finalizações dos últimos 4 jogos
    chutes_casa_historico = []
    for jogo in jogos_casa[:4]:
        total = _extrair_stats_jogo(jogo, time_id_casa, 'Total Shots')
        no_gol = _extrair_stats_jogo(jogo, time_id_casa, 'Shots on Goal')
        if total and no_gol:
            chutes_casa_historico.append({
                'total': total['time'],
                'no_gol': no_gol['time'],
                'adversario': total['adversario']
            })
    
    chutes_fora_historico = []
    for jogo in jogos_fora[:4]:
        total = _extrair_stats_jogo(jogo, time_id_fora, 'Total Shots')
        no_gol = _extrair_stats_jogo(jogo, time_id_fora, 'Shots on Goal')
        if total and no_gol:
            chutes_fora_historico.append({
                'total': total['time'],
                'no_gol': no_gol['time'],
                'adversario': total['adversario']
            })
    
    if not chutes_casa_historico and not chutes_fora_historico:
        return "📖 JUSTIFICATIVA:\n✅ CONCLUSÃO: Estatísticas favoráveis para este mercado."
    
    # Formatar dados dos jogos
    texto = "📖 JUSTIFICATIVA:\n\n"
    texto += "📊 <b>ÚLTIMOS 4 JOGOS - FINALIZAÇÕES:</b>\n\n"
    
    if chutes_casa_historico:
        nome_casa = jogos_casa[0].get('teams', {}).get('home' if jogos_casa[0].get('teams', {}).get('home', {}).get('id') == time_id_casa else 'away', {}).get('name', 'Casa')
        texto += f"🏠 <b>{nome_casa}:</b>\n"
        for i, dados in enumerate(chutes_casa_historico, 1):
            texto += f"   {i}. {dados['total']} chutes ({dados['no_gol']} no gol) vs {dados['adversario'][:20]}\n"
        
        media_total = sum(d['total'] for d in chutes_casa_historico) / len(chutes_casa_historico)
        media_gol = sum(d['no_gol'] for d in chutes_casa_historico) / len(chutes_casa_historico)
        texto += f"   <b>Média:</b> {media_total:.1f} chutes ({media_gol:.1f} no gol)\n\n"
    
    if chutes_fora_historico:
        nome_fora = jogos_fora[0].get('teams', {}).get('home' if jogos_fora[0].get('teams', {}).get('home', {}).get('id') == time_id_fora else 'away', {}).get('name', 'Fora')
        texto += f"✈️ <b>{nome_fora}:</b>\n"
        for i, dados in enumerate(chutes_fora_historico, 1):
            texto += f"   {i}. {dados['total']} chutes ({dados['no_gol']} no gol) vs {dados['adversario'][:20]}\n"
        
        media_total = sum(d['total'] for d in chutes_fora_historico) / len(chutes_fora_historico)
        media_gol = sum(d['no_gol'] for d in chutes_fora_historico) / len(chutes_fora_historico)
        texto += f"   <b>Média:</b> {media_total:.1f} chutes ({media_gol:.1f} no gol)\n\n"
    
    # Gerar conclusão convincente baseada nos dados
    texto += _gerar_conclusao_chutes(chutes_casa_historico, chutes_fora_historico, resultado)
    
    return texto


def _formatar_justificativa_gols(jogos_casa, jogos_fora, time_id_casa, time_id_fora, resultado):
    """Formata justificativa específica para mercado de gols."""
    
    # Extrair dados de gols dos últimos 4 jogos
    gols_casa_historico = []
    for jogo in jogos_casa[:4]:
        teams_info = jogo.get('teams', {})
        home_id = teams_info.get('home', {}).get('id')
        is_home = home_id == time_id_casa
        
        gols_marcados = jogo.get('home_goals' if is_home else 'away_goals', 0)
        gols_sofridos = jogo.get('away_goals' if is_home else 'home_goals', 0)
        adversario = teams_info.get('away' if is_home else 'home', {}).get('name', 'N/A')
        
        gols_casa_historico.append({
            'marcados': gols_marcados,
            'sofridos': gols_sofridos,
            'total': gols_marcados + gols_sofridos,
            'adversario': adversario
        })
    
    gols_fora_historico = []
    for jogo in jogos_fora[:4]:
        teams_info = jogo.get('teams', {})
        home_id = teams_info.get('home', {}).get('id')
        is_home = home_id == time_id_fora
        
        gols_marcados = jogo.get('home_goals' if is_home else 'away_goals', 0)
        gols_sofridos = jogo.get('away_goals' if is_home else 'home_goals', 0)
        adversario = teams_info.get('away' if is_home else 'home', {}).get('name', 'N/A')
        
        gols_fora_historico.append({
            'marcados': gols_marcados,
            'sofridos': gols_sofridos,
            'total': gols_marcados + gols_sofridos,
            'adversario': adversario
        })
    
    # Formatar dados dos jogos
    texto = "📖 JUSTIFICATIVA:\n\n"
    texto += "📊 <b>ÚLTIMOS 4 JOGOS - GOLS:</b>\n\n"
    
    if gols_casa_historico:
        nome_casa = jogos_casa[0].get('teams', {}).get('home' if jogos_casa[0].get('teams', {}).get('home', {}).get('id') == time_id_casa else 'away', {}).get('name', 'Casa')
        texto += f"🏠 <b>{nome_casa}:</b>\n"
        for i, dados in enumerate(gols_casa_historico, 1):
            texto += f"   {i}. {dados['marcados']} gols marcados, {dados['sofridos']} sofridos (Total: {dados['total']}) vs {dados['adversario'][:20]}\n"
        
        media_marcados = sum(d['marcados'] for d in gols_casa_historico) / len(gols_casa_historico)
        media_sofridos = sum(d['sofridos'] for d in gols_casa_historico) / len(gols_casa_historico)
        texto += f"   <b>Média:</b> {media_marcados:.1f} gols marcados | {media_sofridos:.1f} sofridos\n\n"
    
    if gols_fora_historico:
        nome_fora = jogos_fora[0].get('teams', {}).get('home' if jogos_fora[0].get('teams', {}).get('home', {}).get('id') == time_id_fora else 'away', {}).get('name', 'Fora')
        texto += f"✈️ <b>{nome_fora}:</b>\n"
        for i, dados in enumerate(gols_fora_historico, 1):
            texto += f"   {i}. {dados['marcados']} gols marcados, {dados['sofridos']} sofridos (Total: {dados['total']}) vs {dados['adversario'][:20]}\n"
        
        media_marcados = sum(d['marcados'] for d in gols_fora_historico) / len(gols_fora_historico)
        media_sofridos = sum(d['sofridos'] for d in gols_fora_historico) / len(gols_fora_historico)
        texto += f"   <b>Média:</b> {media_marcados:.1f} gols marcados | {media_sofridos:.1f} sofridos\n\n"
    
    # Gerar conclusão convincente baseada nos dados
    texto += _gerar_conclusao_gols(gols_casa_historico, gols_fora_historico, resultado)
    
    return texto


def _gerar_conclusao_cantos(casa_hist, fora_hist, resultado):
    """Gera conclusão convincente para cantos baseada nos dados reais."""
    if not casa_hist and not fora_hist:
        return "✅ CONCLUSÃO: Estatísticas favoráveis."
    
    tipo = resultado.get('tipo', '')
    
    # Calcular médias e tendências
    if casa_hist:
        media_casa = sum(d['time'] for d in casa_hist) / len(casa_hist)
        consistencia_casa = len([d for d in casa_hist if d['time'] >= media_casa * 0.8]) / len(casa_hist)
    else:
        media_casa = 0
        consistencia_casa = 0
    
    if fora_hist:
        media_fora = sum(d['time'] for d in fora_hist) / len(fora_hist)
        consistencia_fora = len([d for d in fora_hist if d['time'] >= media_fora * 0.8]) / len(fora_hist)
    else:
        media_fora = 0
        consistencia_fora = 0
    
    media_total = media_casa + media_fora
    
    if 'Over' in tipo:
        if consistencia_casa >= 0.75 or consistencia_fora >= 0.75:
            return f"✅ CONCLUSÃO: <b>ALTÍSSIMA PROBABILIDADE</b>. Ambos os times mantêm REGULARIDADE elevada em escanteios ({media_total:.1f} média combinada). Padrão consistente nos últimos 4 jogos indica forte tendência de ultrapassar a linha."
        elif media_total >= 10:
            return f"✅ CONCLUSÃO: <b>MUITO FAVORÁVEL</b>. Média combinada de {media_total:.1f} escanteios/jogo supera significativamente a linha. Histórico recente mostra times ofensivos com pressão constante."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Média de {media_total:.1f} escanteios sugere boa probabilidade. Pressão ofensiva recente indica potencial para superar a linha."
    else:  # Under
        jogos_baixos = len([d for d in casa_hist + fora_hist if d['time'] <= 5])
        if jogos_baixos >= len(casa_hist + fora_hist) * 0.75:
            return f"✅ CONCLUSÃO: <b>FORTE PADRÃO</b>. Em {jogos_baixos} dos últimos {len(casa_hist + fora_hist)} jogos houve POUCOS escanteios. Tendência clara de jogos com baixa pressão ofensiva."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Média de {media_total:.1f} escanteios sugere jogo controlado com poucas finalizações forçadas."


def _gerar_conclusao_cartoes(casa_hist, fora_hist, resultado):
    """Gera conclusão convincente para cartões baseada nos dados reais."""
    if not casa_hist and not fora_hist:
        return "✅ CONCLUSÃO: Estatísticas favoráveis."
    
    tipo = resultado.get('tipo', '')
    
    if casa_hist:
        media_casa = sum(d['total'] for d in casa_hist) / len(casa_hist)
        jogos_violentos_casa = len([d for d in casa_hist if d['total'] >= 3])
    else:
        media_casa = 0
        jogos_violentos_casa = 0
    
    if fora_hist:
        media_fora = sum(d['total'] for d in fora_hist) / len(fora_hist)
        jogos_violentos_fora = len([d for d in fora_hist if d['total'] >= 3])
    else:
        media_fora = 0
        jogos_violentos_fora = 0
    
    media_total = media_casa + media_fora
    jogos_violentos_total = jogos_violentos_casa + jogos_violentos_fora
    
    if 'Over' in tipo:
        if jogos_violentos_total >= 5:
            return f"✅ CONCLUSÃO: <b>PROBABILIDADE MUITO ALTA</b>. {jogos_violentos_total} dos últimos 8 jogos tiveram 3+ cartões. Times demonstram jogo duro e MUITAS FALTAS, indicando arbitragem rigorosa necessária."
        elif media_total >= 5:
            return f"✅ CONCLUSÃO: <b>FORTE TENDÊNCIA</b>. Média de {media_total:.1f} cartões/jogo indica confrontos intensos. Padrão de jogo físico com faltas frequentes."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Média de {media_total:.1f} cartões sugere jogo movimentado com arbitragem presente."
    else:  # Under
        jogos_limpos = len([d for d in casa_hist + fora_hist if d['total'] <= 2])
        if jogos_limpos >= 6:
            return f"✅ CONCLUSÃO: <b>PADRÃO CLARO</b>. {jogos_limpos} jogos com POUCOS cartões nos últimos 8 confrontos. Times jogam limpo com poucas faltas."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Histórico indica jogo técnico com baixa intensidade física."


def _gerar_conclusao_chutes(casa_hist, fora_hist, resultado):
    """Gera conclusão convincente para finalizações baseada nos dados reais."""
    if not casa_hist and not fora_hist:
        return "✅ CONCLUSÃO: Estatísticas favoráveis."
    
    tipo = resultado.get('tipo', '')
    
    if casa_hist:
        media_total_casa = sum(d['total'] for d in casa_hist) / len(casa_hist)
        media_gol_casa = sum(d['no_gol'] for d in casa_hist) / len(casa_hist)
    else:
        media_total_casa = 0
        media_gol_casa = 0
    
    if fora_hist:
        media_total_fora = sum(d['total'] for d in fora_hist) / len(fora_hist)
        media_gol_fora = sum(d['no_gol'] for d in fora_hist) / len(fora_hist)
    else:
        media_total_fora = 0
        media_gol_fora = 0
    
    media_total_combinada = media_total_casa + media_total_fora
    media_gol_combinada = media_gol_casa + media_gol_fora
    
    if 'Over' in tipo:
        if media_total_combinada >= 25:
            return f"✅ CONCLUSÃO: <b>ALTÍSSIMA PROBABILIDADE</b>. Média de {media_total_combinada:.1f} finalizações/jogo ({media_gol_combinada:.1f} no gol). Times MUITO OFENSIVOS com volume alto de tentativas."
        elif media_total_combinada >= 20:
            return f"✅ CONCLUSÃO: <b>MUITO FAVORÁVEL</b>. Combinado de {media_total_combinada:.1f} finalizações indica times que atacam constantemente e criam muitas chances."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Média de {media_total_combinada:.1f} finalizações sugere bom volume ofensivo."
    else:  # Under
        if media_total_combinada <= 18:
            return f"✅ CONCLUSÃO: <b>FORTE PADRÃO</b>. Apenas {media_total_combinada:.1f} finalizações/jogo em média. Times pouco criativos com BAIXO volume de tentativas."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Histórico indica jogo cadenciado com poucas finalizações."


def _gerar_conclusao_gols(casa_hist, fora_hist, resultado):
    """Gera conclusão convincente para gols baseada nos dados reais."""
    if not casa_hist and not fora_hist:
        return "✅ CONCLUSÃO: Estatísticas favoráveis."
    
    tipo = resultado.get('tipo', '')
    
    if casa_hist:
        media_total_casa = sum(d['total'] for d in casa_hist) / len(casa_hist)
        media_marcados_casa = sum(d['marcados'] for d in casa_hist) / len(casa_hist)
        jogos_over_casa = len([d for d in casa_hist if d['total'] >= 3])
    else:
        media_total_casa = 0
        media_marcados_casa = 0
        jogos_over_casa = 0
    
    if fora_hist:
        media_total_fora = sum(d['total'] for d in fora_hist) / len(fora_hist)
        media_marcados_fora = sum(d['marcados'] for d in fora_hist) / len(fora_hist)
        jogos_over_fora = len([d for d in fora_hist if d['total'] >= 3])
    else:
        media_total_fora = 0
        media_marcados_fora = 0
        jogos_over_fora = 0
    
    media_total_combinada = (media_total_casa + media_total_fora) / 2
    jogos_over_total = jogos_over_casa + jogos_over_fora
    
    if 'Over' in tipo:
        if jogos_over_total >= 5:
            return f"✅ CONCLUSÃO: <b>PROBABILIDADE MUITO ALTA</b>. {jogos_over_total} dos últimos 8 jogos tiveram 3+ gols. Média de {media_total_combinada:.1f} gols/jogo indica DEFESAS FRÁGEIS e ataques eficientes."
        elif media_total_combinada >= 3:
            return f"✅ CONCLUSÃO: <b>MUITO FAVORÁVEL</b>. Média de {media_total_combinada:.1f} gols/jogo. Times marcam {media_marcados_casa:.1f} e {media_marcados_fora:.1f} respectivamente, indicando ataque forte."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Padrão ofensivo com média de {media_total_combinada:.1f} gols sugere boa probabilidade de ultrapassar a linha."
    else:  # Under
        jogos_under = len([d for d in casa_hist + fora_hist if d['total'] <= 2])
        if jogos_under >= 6:
            return f"✅ CONCLUSÃO: <b>PADRÃO MUITO FORTE</b>. {jogos_under} dos últimos 8 jogos com POUCOS gols. Defesas sólidas e ataques ineficientes."
        else:
            return f"✅ CONCLUSÃO: <b>FAVORÁVEL</b>. Média de {media_total_combinada:.1f} gols indica jogo equilibrado e controlado."
