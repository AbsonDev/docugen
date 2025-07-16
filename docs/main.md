**Main CLI Interface for Auto-Docs**
=====================================

**Visão Geral Completa**
------------------------

O arquivo `main.py` é a interface de linha de comando (CLI) principal para o auto-docs, um ferramenta de geração de documentação automatizada para projetos Python. Ele fornece uma interface para analisar repositórios, gerar documentação e gerenciar hooks Git.

**Responsabilidades Principais**

* Gerenciar a interface de linha de comando para o auto-docs
* Analisar repositórios e gerar documentação
* Gerenciar hooks Git para automaticamente gerar documentação
* Fornece opções de configuração e personalização para o usuário

**Análise Técnica Profunda**
---------------------------

### load_environment()

Carrega variáveis de ambiente do arquivo `.env`.

**Parâmetros de Entrada**

* Nenhum

**Valores de Retorno**

* Uma dicionário com as variáveis de ambiente carregadas

**Possíveis Exceções e Tratamento de Erros**

* Erro ao carregar o arquivo `.env`

### get_api_key()

Recupera a chave API do Groq a partir das variáveis de ambiente ou solicita ao usuário.

**Parâmetros de Entrada**

* Nenhum

**Valores de Retorno**

* A chave API do Groq

**Possíveis Exceções e Tratamento de Erros**

* Erro ao carregar a chave API do Groq

### create_doc_generator(config_overrides)

Cria uma instância do gerador de documentação com configurações personalizadas.

**Parâmetros de Entrada**

* `config_overrides`: Dicionário com configurações personalizadas

**Valores de Retorno**

* Uma instância do gerador de documentação

**Possíveis Exceções e Tratamento de Erros**

* Erro ao criar a instância do gerador de documentação

### cli(ctx, verbose, quiet)

Interface de linha de comando para o auto-docs.

**Parâmetros de Entrada**

* `ctx`: Contexto da execução
* `verbose`: Nível de verbosidade
* `quiet`: Nível de quietude

**Valores de Retorno**

* Nenhum

**Possíveis Exceções e Tratamento de Erros**

* Erro ao executar a interface de linha de comando

### analyze(ctx, repo, output, format, include_examples, include_complexity, max_files, organized, chunk_size, priority_only)

Analisar repositório e gerar documentação.

**Parâmetros de Entrada**

* `ctx`: Contexto da execução
* `repo`: Caminho do repositório
* `output`: Caminho de saída da documentação
* `format`: Formato de saída da documentação
* `include_examples`: Incluir exemplos na documentação
* `include_complexity`: Incluir complexidade na documentação
* `max_files`: Limite de arquivos a serem analisados
* `organized`: Organizar a documentação por seção
* `chunk_size`: Tamanho do chunk para a análise
* `priority_only`: Priorizar apenas os arquivos mais importantes

**Valores de Retorno**

* Nenhum

**Possíveis Exceções e Tratamento de Erros**

* Erro ao analisar o repositório

### organize(ctx, repo, output, max_files, chunk_size, priority_only)

Gerar documentação organizada para o repositório.

**Parâmetros de Entrada**

* `ctx`: Contexto da execução
* `repo`: Caminho do repositório
* `output`: Caminho de saída da documentação
* `max_files`: Limite de arquivos a serem analisados
* `chunk_size`: Tamanho do chunk para a análise
* `priority_only`: Priorizar apenas os arquivos mais importantes

**Valores de Retorno**

* Nenhum

**Possíveis Exceções e Tratamento de Erros**

* Erro ao gerar a documentação

### install_hook(ctx, repo, hook_type, force)

Instalar hook Git para automaticamente gerar documentação.

**Parâmetros de Entrada**

* `ctx`: Contexto da execução
* `repo`: Caminho do repositório
* `hook_type`: Tipo do hook a ser instalado
* `force`: Forçar a instalação do hook

**Valores de Retorno**

* Nenhum

**Possíveis Exceções e Tratamento de Erros**

* Er