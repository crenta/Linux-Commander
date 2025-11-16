import requests
import json
import settings_manager

# --- SHARED PROMPTS ---
SYSTEM_PROMPT = (
    "You are a senior Linux systems engineer. When providing man page links, "
    "use https://linux.die.net/man/1/COMMAND for most commands. "
    "Be concise but thorough."
)

def _get_user_prompt(command):
    return f"""Analyze this Linux command:
Command: {command}

Provide:
1. **Syntax Check**: Will it execute? Missing args?
2. **Explanation**: What it does, key flags inline.
3. **Issues**: Potential problems/dangers.
4. **Alternatives/Tips**: (Optional) Modern alternatives or cybersecurity tips.
5. **Improved Command**: ONE corrected version as a code block.
6. **Reference**: Man page URL.
Be concise."""

def analyze_command(command_to_analyze: str) -> str:
    """
    Main router function. Loads settings and dispatches to the active provider.
    """
    settings = settings_manager.load_settings()
    provider = settings.get("active_provider", "Mistral")
    api_key = settings["api_keys"].get(provider, "")
    model = settings["models"].get(provider, "")

    if not api_key:
        return f"⚠️ ERROR: No API Key found for {provider}.\n\nPlease click 'AI Settings' and enter your key."

    try:
        if provider == "Mistral":
            return _analyze_with_mistral(api_key, model, command_to_analyze)
        elif provider == "OpenAI":
            return _analyze_with_openai(api_key, model, command_to_analyze)
        elif provider == "Gemini":
            return _analyze_with_gemini(api_key, model, command_to_analyze)
        elif provider == "Claude":
            return _analyze_with_claude(api_key, model, command_to_analyze)
        else:
            return f"ERROR: Unknown provider selected: {provider}"
            
    except requests.exceptions.RequestException as e:
        return f"NETWORK ERROR ({provider}):\n{e}"
    except Exception as e:
        return f"UNKNOWN ERROR ({provider}):\n{e}"

# =========================================
# === PROVIDER IMPLEMENTATIONS ===
# =========================================

def _analyze_with_mistral(api_key, model, command):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _get_user_prompt(command)}
        ],
        "max_tokens": 600
    }
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    message = result['choices'][0]['message']['content']
    usage = result.get('usage', {}).get('total_tokens', 'N/A')
    return f"{message}\n\n---\nTokens Used: {usage}"

def _analyze_with_openai(api_key, model, command):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _get_user_prompt(command)}
        ],
        "temperature": 0.3,
        "max_tokens": 600
    }
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    message = result['choices'][0]['message']['content']
    usage = result.get('usage', {}).get('total_tokens', 'N/A')
    return f"{message}\n\n---\nTokens Used: {usage}"

def _analyze_with_claude(api_key, model, command):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": _get_user_prompt(command)}
        ],
        "max_tokens": 600
    }
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    message = result['content'][0]['text']
    usage_data = result.get('usage', {})
    input_tokens = usage_data.get('input_tokens', 0)
    output_tokens = usage_data.get('output_tokens', 0)
    total_usage = input_tokens + output_tokens if (input_tokens or output_tokens) else 'N/A'
    
    return f"{message}\n\n---\nTokens Used: {total_usage}"

def _analyze_with_gemini(api_key, model, command):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    full_prompt = f"{SYSTEM_PROMPT}\n\nIMPORTANT: {_get_user_prompt(command)}"
    
    data = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 600,
            "temperature": 0.4
        }
    }
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    try:
        message = result['candidates'][0]['content']['parts'][0]['text']
        usage = result.get('usageMetadata', {}).get('totalTokenCount', 'N/A')
        return f"{message}\n\n---\nTokens Used: {usage}"
    except (KeyError, IndexError):
        return f"Gemini Error: Unexpected response format.\n{json.dumps(result, indent=2)}"
