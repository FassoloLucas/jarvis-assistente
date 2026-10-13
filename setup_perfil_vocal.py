"""Cadastra o perfil vocal do chefe — roda uma única vez (ou de novo pra
recadastrar). Depois disso, o J.A.R.V.I.S. passa a recusar comandos ditos
por qualquer voz que não bata com esse perfil (veja jarvis/voz_biometria.py).

Sem rodar este script, o recurso fica desligado e o J.A.R.V.I.S. continua
funcionando normalmente pra qualquer voz — como sempre foi.

Pré-requisito: dependências extras instaladas na venv do projeto (torch,
resemblyzer, etc. — veja a seção "Biometria de voz" no README).

Uso:
    .venv\\Scripts\\python.exe setup_perfil_vocal.py
"""

import speech_recognition as sr

from jarvis import voz_biometria

FRASE_SUGERIDA = (
    "Jarvis, esse é o meu perfil de voz. A partir de agora, "
    "reconheça sempre que for eu falando com você."
)


def main():
    print("=== Cadastro de perfil vocal do J.A.R.V.I.S. ===\n")
    print("Fale em voz alta e naturalmente por uns 10 segundos, algo como:")
    print(f'  "{FRASE_SUGERIDA}"\n')
    input("Pressione Enter e comece a falar assim que aparecer 'Gravando...'.")

    reconhecedor = sr.Recognizer()
    with sr.Microphone() as fonte:
        print("Ajustando ao ruído ambiente...")
        reconhecedor.adjust_for_ambient_noise(fonte, duration=1)
        print("Gravando... (fale agora)")
        audio = reconhecedor.listen(fonte, phrase_time_limit=12)

    print("Processando o perfil de voz...")
    voz_biometria.cadastrar_perfil(audio.get_wav_data())
    print(f"\nPronto! Perfil salvo em {voz_biometria.CAMINHO_PERFIL}.")
    print("A partir de agora, o J.A.R.V.I.S. só executa comandos com essa voz.")
    print("Não ficou bom? Rode este script de novo pra recadastrar.")


if __name__ == "__main__":
    main()
