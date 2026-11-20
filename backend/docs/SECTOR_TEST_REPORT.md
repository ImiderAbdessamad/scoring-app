# Rapport de tests — analyse sectorielle

Commandes :

```
cd backend
py -3 -m pytest tests/test_sector_analysis.py tests/test_wfb_finalisation.py -q

cd frontend
npm test
```

Couverture backend : 36 tests sector + régression wfb/synthese.

Frontend : 45 tests (vitest), dont labels Analyse sectorielle / Comportement bancaire et formatter.
