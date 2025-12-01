# Instruções para agentes (Atualize este arquivo sempre que necessário)

- Este projeto usa Flask com SQLite; prefira manter a simplicidade e evite adicionar frameworks desnecessários sem alinhamento prévio.
- Use o app factory `create_app` em `app.py` para inicializar a aplicação e facilitar testes.
- O módulo `database.py` concentra utilidades de conexão; mantenha-o livre de lógica de apresentação.
- Comentários marcados como "(Atualizar se necessário)" devem ser revisados sempre que o comportamento associado mudar.
- Ao modificar templates, preserve a navegação básica (Dashboard, Lançamentos, Consultas) e mantenha o Chart.js carregado apenas na página do dashboard.
- Sempre atualize esta AGENTS.MD quando novas convenções surgirem.
