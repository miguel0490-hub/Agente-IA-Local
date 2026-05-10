def search_web(query: str, max_results: int = 5) -> str:
    """
    Realiza una búsqueda en DuckDuckGo y devuelve un resumen formateado
    de los primeros resultados para inyectar al LLM.
    """
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"Búsqueda web sin resultados para: '{query}'"
            
        formatted_results = f"### Resultados Web de la búsqueda: '{query}'\n\n"
        for i, res in enumerate(results, 1):
            title = res.get('title', 'Sin Título')
            href = res.get('href', 'Sin URL')
            body = res.get('body', 'Sin contenido')
            
            formatted_results += f"**[{i}] {title}**\n"
            formatted_results += f"URL: {href}\n"
            formatted_results += f"Resumen: {body}\n\n"
            
        return formatted_results.strip()
    except ModuleNotFoundError:
        return (
            "Error en la búsqueda web: falta la dependencia 'ddgs'. "
            "Instálala con: pip install ddgs"
        )
    except Exception as e:
        return f"Error en la búsqueda web: {str(e)}"
