\# JARVIS — Assistente Pessoal Inteligente



Um assistente pessoal para Windows, desenvolvido em Python, com interface gráfica, inteligência artificial, reconhecimento de voz, síntese de fala e memória persistente.



O objetivo do projeto é construir um assistente inspirado no JARVIS do universo Iron Man, combinando automação local e inteligência artificial conectada à internet.



\## Funcionalidades



\- Interface gráfica desenvolvida com PySide6.

\- Integração com a API Gemini.

\- Conversação com inteligência artificial.

\- Modo de conversa por voz em tempo real.

\- Reconhecimento de fala com Faster Whisper.

\- Síntese de voz com Piper TTS.

\- Memória persistente utilizando SQLite.

\- Recuperação de conversas anteriores.

\- Abertura de aplicativos instalados no Windows.

\- Pesquisa na internet.

\- Ferramentas para executar tarefas autorizadas.

\- Monitoramento de informações do sistema.



> O projeto está em desenvolvimento. Algumas funcionalidades dependem de configurações locais, permissões e disponibilidade dos serviços externos.



\## Tecnologias utilizadas



\- Python

\- PySide6

\- Google Gemini API

\- Google GenAI SDK

\- SQLite

\- Faster Whisper

\- Piper TTS

\- NumPy

\- SciPy

\- SoundDevice

\- Requests



\## Requisitos



\- Windows 10 ou Windows 11.

\- Python instalado.

\- Conexão com a internet para utilizar os recursos Gemini.

\- Microfone e dispositivo de saída de áudio para os recursos de voz.

\- Chave própria da API Gemini.



\## Instalação



\### 1. Clonar o repositório



```powershell

git clone https://github.com/cyber-jhonny/reactive_proje.git

```



Entre na pasta:



```powershell

cd JARVIS

```



\### 2. Criar o ambiente virtual



```powershell

py -m venv .venv

```



\### 3. Instalar as dependências



```powershell

.\\.venv\\Scripts\\python.exe -m pip install --upgrade pip

.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt

```



\### 4. Configurar a API Gemini



Copie o arquivo de exemplo:



```powershell

Copy-Item .env.example .env

```



Abra o arquivo:



```powershell

notepad .env

```



Adicione sua chave:



```env

GEMINI\_API\_KEY=SUA\_CHAVE\_GEMINI

```



Você pode obter uma chave pelo Google AI Studio:



https://aistudio.google.com/apikey



\*\*Nunca compartilhe sua chave ou publique o arquivo `.env`.\*\*



\### 5. Iniciar o JARVIS



Execute:



```powershell

.\\.venv\\Scripts\\python.exe interface.py

```



\## Estrutura do projeto



```text

JARVIS/

│

├── dados/

│   └── catalogo\_aplicativos.json

│

├── modelo/

│   └── Modelos de reconhecimento de voz

│

├── modulos/

│   ├── caminhos.py

│   ├── memoria.py

│   ├── memoria\_contextual.py

│   ├── inteligencia.py

│   ├── internet.py

│   ├── aplicativos.py

│   └── conversa\_ao\_vivo.py

│

├── monitoramento/

│   └── sensores.py

│

├── voz/

│   ├── escutar.py

│   ├── falar.py

│   ├── reconhecer\_voz.py

│   └── modelos/

│

├── interface.py

├── jarvis.py

├── requirements.txt

├── .env.example

└── README.md

```



\## Privacidade e segurança



\- As chaves de API devem permanecer em arquivos locais não publicados.

\- A memória das conversas utiliza banco de dados SQLite local.

\- Arquivos pessoais e configurações locais não devem ser enviados ao repositório.

\- Ações sensíveis devem exigir autorização do usuário.

\- Nunca compartilhe tokens, senhas ou informações privadas.



\## Contribuições



Contribuições são bem-vindas!



1\. Faça um fork do projeto.

2\. Crie uma branch para sua alteração.

3\. Implemente e teste suas melhorias.

4\. Envie um Pull Request explicando suas mudanças.



\## Objetivo



Evoluir o JARVIS continuamente, adicionando recursos de inteligência artificial, automação, memória, interação por voz e integração com o Windows.



Projeto independente, desenvolvido em Python.

