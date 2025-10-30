# cache_manager.py
import json
import os
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 🇧🇷 HORÁRIO DE BRASÍLIA: Todas as operações de datetime usam timezone de Brasília
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

def agora_brasilia():
    """Retorna datetime atual no horário de Brasília"""
    return datetime.now(BRASILIA_TZ)

_cache = {}
_cache_lock = threading.RLock()  # RLock (reentrant) para evitar deadlocks
CACHE_FILE = "cache.json"

# Configurações inteligentes de expiração por tipo de dado
# 🚀 CACHE ULTRA-AGRESSIVO: Todos com 24 horas para máxima performance
CACHE_EXPIRATION = {
    'jogos_': 1440,              # 24 HORAS - jogos do dia
    'odds_': 1440,               # 24 HORAS - odds
    'stats_': 1440,              # 24 HORAS - estatísticas de times
    'classificacao_': 1440,      # 24 HORAS - classificação
    'analise_jogo_': 1440,       # 24 HORAS - análise completa de jogo
    'fixture_stats_': 1440,      # 24 HORAS - estatísticas de fixture
    'ultimos_jogos_': 1440,      # 24 HORAS - últimos jogos do time
    'ligas_': 1440,              # 24 HORAS - lista de ligas disponíveis
    'h2h_': 1440,                # 24 HORAS - confrontos diretos (H2H)
    'default': 1440              # 24 HORAS - padrão
}

def get_expiration_for_key(key):
    """Determina tempo de expiração baseado no prefixo da chave"""
    for prefix, minutes in CACHE_EXPIRATION.items():
        if key.startswith(prefix):
            return minutes
    return CACHE_EXPIRATION['default']

def set(key, value, expiration_minutes=None):
    """
    Adiciona um valor ao cache com tempo de expiração inteligente.
    Se não especificar tempo, usa valores otimizados por tipo.
    """
    global _cache

    if expiration_minutes is None:
        expiration_minutes = get_expiration_for_key(key)

    now = agora_brasilia()
    expiration_time = now + timedelta(minutes=expiration_minutes)

    with _cache_lock:
        _cache[key] = {
            "value": value, 
            "expires_at": expiration_time.isoformat(),
            "created_at": now.isoformat()
        }
    save_cache_to_disk()

def get(key):
    """
    Busca um valor no cache, verificando se não expirou.
    """
    global _cache
    with _cache_lock:
        data = _cache.get(key)

        if not data:
            return None

        if data.get("expires_at"):
            try:
                expiration_time = datetime.fromisoformat(data["expires_at"])
                if agora_brasilia() > expiration_time:
                    del _cache[key]
                    save_cache_to_disk()
                    return None
            except (TypeError, ValueError):
                 pass

        return data.get("value")

def clear():
    """Limpa todo o cache"""
    global _cache
    with _cache_lock:
        _cache = {}
    save_cache_to_disk()
    print("✅ CACHE CLEARED: Toda memória foi limpa!")

def get_stats():
    """Retorna estatísticas do cache sem alterar o dict durante iteração"""
    global _cache
    total = len(_cache)
    # Iterar sobre cópia para evitar RuntimeError
    cache_items = list(_cache.items())
    validos = 0

    for key, data in cache_items:
        if data.get("expires_at"):
            try:
                expiration_time = datetime.fromisoformat(data["expires_at"])
                if agora_brasilia() <= expiration_time:
                    validos += 1
            except (TypeError, ValueError):
                validos += 1  # Contar como válido se não tem expiração
        else:
            validos += 1

    expirados = total - validos
    return {
        'total': total,
        'validos': validos,
        'expirados': expirados
    }

def save_cache_to_disk():
    """Salva o conteúdo do cache em um arquivo JSON"""
    global _cache
    try:
        with _cache_lock:
            cache_copy = _cache.copy()  # Criar cópia para evitar race condition

        with open(CACHE_FILE, 'w') as f:
            if cache_copy:
                json.dump(cache_copy, f, indent=4)
            else:
                f.write('{}')
    except Exception as e:
        print(f"❌ ERRO ao salvar o cache em disco: {e}")

def cleanup_expired():
    """
    Remove itens expirados do cache para liberar memória.
    Executado automaticamente ao carregar o cache.
    """
    global _cache
    removidos = 0

    with _cache_lock:
        keys_to_remove = []
        for key, data in _cache.items():
            if data.get("expires_at"):
                try:
                    expiration_time = datetime.fromisoformat(data["expires_at"])
                    if agora_brasilia() > expiration_time:
                        keys_to_remove.append(key)
                except (TypeError, ValueError):
                    pass

        for key in keys_to_remove:
            del _cache[key]
            removidos += 1

    if removidos > 0:
        save_cache_to_disk()
        print(f"🧹 CACHE CLEANUP: {removidos} itens expirados removidos")

    return removidos

def load_cache_from_disk():
    """Carrega o cache do arquivo JSON ao iniciar o bot"""
    global _cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                content = f.read()
                if content:
                    _cache = json.loads(content)
                    # Limpar expirados ao carregar
                    cleanup_expired()
                    stats = get_stats()
                    print(f"✅ CACHE LOADED: {stats['validos']} itens válidos carregados (Total: {stats['total']})")
                else:
                    _cache = {}
                    print("ℹ️  CACHE vazio. Iniciando com memória limpa.")
        else:
            print("ℹ️  Cache não encontrado. Iniciando com memória limpa.")
    except (json.JSONDecodeError, Exception) as e:
        print(f"❌ ERRO ao carregar cache: {e}")
        _cache = {}
