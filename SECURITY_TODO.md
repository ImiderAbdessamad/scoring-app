# Sécurité — reste à faire

- Remplacer CHANGE_ME MinIO ; ne jamais committer minioadmin en production
- PVC_API_KEY : secret, pas dans .env.example
- Antivirus : NoOpMalwareScanner (status NOT_CONFIGURED)
- Corrélation ID : header X-Correlation-ID ; ne pas logger PDF, CIN, tokens
- SQLite fichier local : permissions OS
- Auth utilisateur (acteur décision) non implémentée
