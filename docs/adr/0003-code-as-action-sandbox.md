# 0003 · Code-as-action dans un sandbox Docker

**Contexte.** Des fonctions figées limiteraient l'espace d'analyse (statistiques et ML).

**Décision.** L'agent écrit du pandas / scikit-learn réellement exécuté. Le code tourne dans
un conteneur sans réseau, racine en lecture seule, utilisateur non privilégié, quotas et
timeout. Sans Docker, on refuse d'exécuter (aucun repli sur l'hôte).

**Conséquences.** Espace d'analyse ouvert, au prix du sandbox, de la boucle critique et
de helpers (`agent_out`) qui compensent un modèle de 14B. Les garanties d'isolation sont
testées pour de vrai en CI.
