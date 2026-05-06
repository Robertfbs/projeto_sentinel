<task>Implementação do Painel de Clima</task>

<role>
    Você é um desenvolvedor full stack senior especializado em React e Node.js e está fazendo a <task> usando a API do Open-Meteo
</role>

<requirements>
    ### Business

    - Exibir o clima atual (temperatura, umidade, vento, UV, precipitação)
    - Previsão de hora em hora (temperatura e precipitação)
    - Previsão para os próximos 7 dias (temperatura mínima e máxima e precipitação)

    ### Technical

    - Implemente nos projetos existentes em ./frontend e ./backend
    - O frontend deve consumir uma API do backend para obter as informações, não deve acessar diretamente a API do Open-Meteo
    - O backend deve fazer as chamadas para o Open-Meteo e fornecer os dados para o frontend
    - A partir da cidade digitada as coordenadas serão descobertas (pela api, no backend) e utilizadas para buscar os dados do clima

    ### UI/UX

    - Design responsivo (mobile-first)
    - Cards com ícones animados para condições climáticas
    - Gráfico interativo para previsão hora a hora
    - Skeleton loading durante carregamento de dados
    - Cores dinâmicas baseadas no clima atual (ex: tons azuis para céu limpo, cinzas para nublado)
    - Barra visual de índice UV com gradiente de cores (verde a vermelho)
    - Cards de 7 dias com barras visuais de temperatura mín/máx
    - Feedback visual para erros com opção de retry
    - Campo de busca de cidade SEM autocomplete
    - Botão de geolocalização para usar localização atual do usuário
    - Feedback visual de loading durante busca
    - Mensagem amigável quando cidade não for encontrada
    - O background deve refletir a temperatura selecionada, use gradient para criar um efeito visual que mostre e relacione a temperatura do local

</requirements>

<endpoints>
    ### Open-Meteo

    - Geocoding API: https://geocoding-api.open-meteo.com/v1/search (converter cidade em coordenadas)
    - Weather API: https://api.open-meteo.com/v1/forecast (obter dados do clima)

    ### Backend

    GET /api/weather?city=<cidade> 200

    Status Code:

    200: Sucesso
    400: Faltam dados
    404: Cidade não encontrada

    Payload: mesmo que retorna do Open-Meteo

</endpoints>

<tests>
    ### Validação de endpoints

    - Faça um curl para testar cada um dos endpoints tanto do Open-Meteo quanto do backend para garantir que estão funcionando

</tests>

<critical>
    ### Skills obrigatórias

    - frontend-design — interfaces de alta qualidade, design distintivo
    - shadcn — componentes UI (cards, inputs, skeletons)
    - ui-ux-pro-max — responsividade, cores dinâmicas, animações, gráficos
    - vercel-react-best-practices — padrões de performance e componentes React
    - web-design-guidelines — acessibilidade e boas práticas de UX

    ### Fora do Escopo

    - *NÃO* implemente tema claro/escuro
    - *NÃO* crie comentários no código
    - *NUNCA* consumir o endpoint direto no frontend

</critical>
