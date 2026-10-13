"""Controle de versão obrigatória do app de celular.

Atualizado manualmente a cada nova versão do app publicada: depois de gerar
o APK (`flutter build apk --release`), copie o arquivo pra
`backend/static/app-release.apk` (sobrescrevendo o anterior) e mude
`VERSAO_MINIMA` aqui pra bater com `version:` do `app/pubspec.yaml` (só a
parte antes do "+", ex: "1.1.0" pra "1.1.0+2").

O app compara essa versão com a instalada (`package_info_plus`) toda vez
que abre — se a instalada for menor, mostra uma tela de atualização
obrigatória (não dá pra pular) que baixa o APK daqui e abre a instalação.
"""

VERSAO_MINIMA = "1.2.0"
