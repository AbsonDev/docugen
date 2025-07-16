"""
AI-powered documentation generator using Groq API.

This module provides functionality to generate comprehensive documentation
for Python code using AI models through the Groq API.
"""

import os
import time
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import groq
from analyzer import ModuleInfo, FunctionInfo, ClassInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DocGenerationConfig:
    """Configuration for documentation generation."""
    model: str = "llama3-8b-8192"
    max_tokens: int = 1000
    temperature: float = 0.3
    max_requests_per_minute: int = 100
    output_format: str = "markdown"
    include_examples: bool = True
    include_type_hints: bool = True
    include_complexity: bool = False


class RateLimiter:
    """Rate limiter for API calls."""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = datetime.now()
        
        # Remove old requests outside time window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(seconds=self.time_window)]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                logger.info(f"Rate limit reached, waiting {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
        
        self.requests.append(now)


class DocGenerator:
    """AI-powered documentation generator using Groq API."""
    
    def __init__(self, api_key: str, config: Optional[DocGenerationConfig] = None):
        """
        Initialize the documentation generator.
        
        Args:
            api_key: Groq API key
            config: Configuration for documentation generation
        """
        self.client = groq.Groq(api_key=api_key)
        self.config = config or DocGenerationConfig()
        self.rate_limiter = RateLimiter(self.config.max_requests_per_minute)
        
        # Cache for generated documentation
        self.doc_cache = {}
    
    def generate_file_docs(self, module_info: ModuleInfo) -> str:
        """
        Generate comprehensive documentation for a Python module.
        
        Args:
            module_info: Information about the module to document
            
        Returns:
            Generated documentation in markdown format
        """
        try:
            # Check cache first
            cache_key = f"{module_info.file_path}_{module_info.last_modified}"
            if cache_key in self.doc_cache:
                return self.doc_cache[cache_key]
            
            prompt = self._create_file_documentation_prompt(module_info)
            
            self.rate_limiter.wait_if_needed()
            
            # Adapt system message based on file type
            if hasattr(module_info, 'file_type') and module_info.file_type == "csharp":
                system_message = "Você é um especialista em documentação técnica. Gere documentação clara e abrangente para código C#/.NET em português brasileiro, usando terminologia técnica apropriada para o ecossistema .NET (Controllers, Services, DTOs, Entity Framework, etc.)."
            else:
                system_message = "Você é um especialista em documentação técnica. Gere documentação clara e abrangente para código Python em português brasileiro, usando terminologia técnica apropriada."
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            documentation = response.choices[0].message.content
            
            # Cache the result
            self.doc_cache[cache_key] = documentation
            
            return documentation
            
        except Exception as e:
            logger.error(f"Error generating documentation for {module_info.file_path}: {e}")
            return self._generate_fallback_documentation(module_info)
    
    def generate_function_docs(self, function_info: FunctionInfo, context: str = "") -> str:
        """
        Generate documentation for a specific function.
        
        Args:
            function_info: Information about the function
            context: Additional context about the function's purpose
            
        Returns:
            Generated function documentation
        """
        try:
            prompt = self._create_function_documentation_prompt(function_info, context)
            
            self.rate_limiter.wait_if_needed()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "Você é um especialista em documentação técnica. Gere documentação clara e concisa para funções Python em português brasileiro, usando terminologia técnica apropriada."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=min(500, self.config.max_tokens),
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating documentation for function {function_info.name}: {e}")
            return self._generate_fallback_function_docs(function_info)
    
    def generate_project_overview(self, modules: Dict[str, ModuleInfo], project_name: str) -> str:
        """
        Generate a comprehensive project overview/README.
        
        Args:
            modules: Dictionary of module information
            project_name: Name of the project
            
        Returns:
            Generated project overview documentation
        """
        try:
            prompt = self._create_project_overview_prompt(modules, project_name)
            
            self.rate_limiter.wait_if_needed()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "Você é um especialista em documentação técnica. Gere documentação profissional de projetos e arquivos README em português brasileiro, usando terminologia técnica apropriada."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens * 2,  # More tokens for project overview
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating project overview: {e}")
            return self._generate_fallback_project_overview(modules, project_name)
    
    def generate_class_docs(self, class_info: ClassInfo, context: str = "") -> str:
        """
        Generate documentation for a specific class.
        
        Args:
            class_info: Information about the class
            context: Additional context about the class's purpose
            
        Returns:
            Generated class documentation
        """
        try:
            prompt = self._create_class_documentation_prompt(class_info, context)
            
            self.rate_limiter.wait_if_needed()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "Você é um especialista em documentação técnica. Gere documentação clara e abrangente para classes Python em português brasileiro, usando terminologia técnica apropriada."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=min(800, self.config.max_tokens),
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating documentation for class {class_info.name}: {e}")
            return self._generate_fallback_class_docs(class_info)
    
    def _create_file_documentation_prompt(self, module_info: ModuleInfo) -> str:
        """Create a prompt for generating file documentation."""
        file_name = Path(module_info.file_path).name
        
        functions_summary = []
        for func in module_info.functions:
            func_args = ", ".join(func.args)
            functions_summary.append(f"- {func.name}({func_args})")
            if func.docstring:
                functions_summary.append(f"  - {func.docstring.split('.')[0]}")
        
        classes_summary = []
        for cls in module_info.classes:
            classes_summary.append(f"- {cls.name}")
            if cls.docstring:
                classes_summary.append(f"  - {cls.docstring.split('.')[0]}")
            if cls.methods:
                classes_summary.append(f"  - Métodos: {', '.join([m.name for m in cls.methods[:5]])}")
        
        imports_list = module_info.imports[:10]  # Limit imports to avoid token overflow
        
        # Adapt prompt based on file type and classification
        if module_info.file_type == "csharp":
            language_context = "C#/.NET"
            classification = getattr(module_info, 'classification', 'unknown')
            
            # Create classification-specific context
            classification_context = self._get_classification_context(classification)
            
            language_specific = f"""
**Namespace:** {module_info.namespace or "Nenhum namespace definido"}
**Classificação:** {classification_context['name']}

**Using Statements:**
{chr(10).join(imports_list) if imports_list else "Nenhum using statement encontrado"}

**Contexto Específico:**
{classification_context['description']}

**Instruções de Documentação:**
{classification_context['instructions']}
"""
        else:
            language_context = "Python"
            language_specific = f"""
**Imports:**
{chr(10).join(imports_list) if imports_list else "Nenhum import encontrado"}
"""
        
        prompt = f"""
Analise este arquivo {language_context} e gere documentação COMPLETA E DETALHADA em português brasileiro:

**Arquivo:** {file_name}
**Caminho:** {module_info.file_path}
**Tipo:** {language_context}

**Documentação do Arquivo:**
{module_info.docstring or "Nenhuma documentação disponível"}

**Funções/Métodos:**
{chr(10).join(functions_summary) if functions_summary else "Nenhuma função encontrada"}

**Classes:**
{chr(10).join(classes_summary) if classes_summary else "Nenhuma classe encontrada"}

{language_specific}

**Constantes:**
{', '.join(module_info.constants) if module_info.constants else "Nenhuma constante encontrada"}

GERE DOCUMENTAÇÃO EXTREMAMENTE DETALHADA incluindo:

## 1. Visão Geral Completa
- Propósito detalhado do arquivo
- Contexto dentro da aplicação
- Responsabilidades principais
- Papel na arquitetura do sistema

## 2. Análise Técnica Profunda
- Descrição detalhada de cada método/função
- Parâmetros de entrada com tipos e exemplos
- Valores de retorno explicados
- Possíveis exceções e tratamento de erros
- Complexidade computacional (quando relevante)

## 3. Exemplos de Uso Práticos
- Exemplos de código completos e funcionais
- Casos de uso comuns
- Cenários de integração
- Patterns de implementação

## 4. Relacionamentos e Dependências
- Dependências externas explicadas
- Relacionamentos com outras classes/módulos
- Injeção de dependências (se aplicável)
- Fluxo de dados entre componentes

## 5. Padrões e Convenções
- Padrões de design utilizados
- Convenções de nomenclatura
- Estrutura de código seguida
- Boas práticas implementadas

## 6. Configuração e Setup
- Configurações necessárias
- Variáveis de ambiente
- Dependências de runtime
- Instruções de inicialização

## 7. Segurança e Validações
- Validações de entrada implementadas
- Aspectos de segurança
- Autorização e autenticação
- Sanitização de dados

## 8. Performance e Otimizações
- Considerações de performance
- Otimizações implementadas
- Possíveis gargalos
- Métricas importantes

## 9. Testes e Qualidade
- Estratégias de teste sugeridas
- Cobertura de testes
- Casos de teste importantes
- Debugging e troubleshooting

## 10. Notas de Implementação
- Decisões arquiteturais
- Limitações conhecidas
- TODOs e melhorias futuras
- Observações importantes

Formato: Markdown profissional com:
- Cabeçalhos hierárquicos claros
- Blocos de código com syntax highlighting
- Tabelas para parâmetros e retornos
- Listas organizadas
- Seções bem estruturadas
- Links internos quando apropriado

Idioma: Português brasileiro com terminologia técnica precisa para {language_context}.
Tom: Técnico, detalhado, mas acessível para desenvolvedores.
"""
        return prompt
    
    def _create_function_documentation_prompt(self, function_info: FunctionInfo, context: str) -> str:
        """Create a prompt for generating function documentation."""
        type_hints_str = ""
        if function_info.type_hints:
            type_hints_str = f"\n**Type Hints:** {json.dumps(function_info.type_hints, indent=2)}"
        
        prompt = f"""
Gere documentação para esta função Python em português brasileiro:

**Função:** {function_info.name}
**Argumentos:** {', '.join(function_info.args)}
**Tipo de Retorno:** {function_info.return_annotation or "Não especificado"}
**É Assíncrona:** {"Sim" if function_info.is_async else "Não"}
**Decoradores:** {', '.join(function_info.decorators) if function_info.decorators else "Nenhum"}
{type_hints_str}

**Docstring Existente:**
{function_info.docstring or "Nenhuma docstring disponível"}

**Contexto:** {context}

Gere documentação clara incluindo:
1. Propósito e funcionalidade
2. Descrição dos parâmetros
3. Explicação do valor de retorno
4. Exemplo de uso
5. Exceções ou casos especiais

Formato: Markdown limpo adequado para documentação técnica.
Idioma: Português brasileiro com terminologia técnica apropriada.
"""
        return prompt
    
    def _create_class_documentation_prompt(self, class_info: ClassInfo, context: str) -> str:
        """Create a prompt for generating class documentation."""
        methods_summary = []
        for method in class_info.methods:
            method_args = ", ".join(method.args)
            methods_summary.append(f"- {method.name}({method_args})")
        
        prompt = f"""
Gere documentação para esta classe Python em português brasileiro:

**Classe:** {class_info.name}
**Classes Base:** {', '.join(class_info.bases) if class_info.bases else "Nenhuma"}
**Decoradores:** {', '.join(class_info.decorators) if class_info.decorators else "Nenhum"}

**Docstring Existente:**
{class_info.docstring or "Nenhuma docstring disponível"}

**Métodos:**
{chr(10).join(methods_summary) if methods_summary else "Nenhum método encontrado"}

**Atributos:**
{', '.join(class_info.attributes) if class_info.attributes else "Nenhum atributo encontrado"}

**Contexto:** {context}

Gere documentação abrangente incluindo:
1. Propósito e funcionalidade da classe
2. Parâmetros do construtor
3. Visão geral dos métodos principais
4. Exemplos de uso
5. Relações de herança
6. Atributos importantes

Formato: Markdown limpo com estrutura apropriada.
Idioma: Português brasileiro com terminologia técnica adequada.
"""
        return prompt
    
    def _create_project_overview_prompt(self, modules: Dict[str, ModuleInfo], project_name: str) -> str:
        """Create a prompt for generating project overview documentation."""
        module_summaries = []
        for path, module in list(modules.items())[:20]:  # Limit to avoid token overflow
            file_name = Path(path).name
            func_count = len(module.functions)
            class_count = len(module.classes)
            module_summaries.append(f"- **{file_name}**: {func_count} funções, {class_count} classes")
        
        prompt = f"""
Gere um README.md abrangente para este projeto Python em português brasileiro:

**Nome do Projeto:** {project_name}
**Total de Módulos:** {len(modules)}

**Estrutura dos Módulos:**
{chr(10).join(module_summaries)}

**Informações Principais a Incluir:**
1. Título e descrição do projeto
2. Instruções de instalação
3. Exemplos de uso básico
4. Visão geral da estrutura do projeto
5. Funcionalidades e recursos principais
6. Requisitos e dependências
7. Diretrizes de contribuição
8. Informações de licença

Gere documentação profissional adequada para um repositório GitHub.
Formato: Markdown limpo com badges, exemplos de código e estrutura clara.
Idioma: Português brasileiro com terminologia técnica adequada.
Tom: Profissional mas acessível para desenvolvedores brasileiros.
"""
        return prompt
    
    def _generate_fallback_documentation(self, module_info: ModuleInfo) -> str:
        """Generate fallback documentation when AI fails."""
        file_name = Path(module_info.file_path).name
        
        doc = f"# {file_name}\n\n"
        
        if module_info.docstring:
            doc += f"{module_info.docstring}\n\n"
        
        if module_info.functions:
            doc += "## Funções\n\n"
            for func in module_info.functions:
                args_str = ", ".join(func.args)
                doc += f"### {func.name}({args_str})\n\n"
                if func.docstring:
                    doc += f"{func.docstring}\n\n"
        
        if module_info.classes:
            doc += "## Classes\n\n"
            for cls in module_info.classes:
                doc += f"### {cls.name}\n\n"
                if cls.docstring:
                    doc += f"{cls.docstring}\n\n"
        
        return doc
    
    def _generate_fallback_function_docs(self, function_info: FunctionInfo) -> str:
        """Generate fallback function documentation."""
        args_str = ", ".join(function_info.args)
        doc = f"### {function_info.name}({args_str})\n\n"
        
        if function_info.docstring:
            doc += f"{function_info.docstring}\n\n"
        else:
            doc += f"Função {function_info.name} com {len(function_info.args)} parâmetros.\n\n"
        
        if function_info.return_annotation:
            doc += f"**Retorna:** {function_info.return_annotation}\n\n"
        
        return doc
    
    def _generate_fallback_class_docs(self, class_info: ClassInfo) -> str:
        """Generate fallback class documentation."""
        doc = f"### {class_info.name}\n\n"
        
        if class_info.docstring:
            doc += f"{class_info.docstring}\n\n"
        else:
            doc += f"Classe {class_info.name} com {len(class_info.methods)} métodos.\n\n"
        
        if class_info.bases:
            doc += f"**Herda de:** {', '.join(class_info.bases)}\n\n"
        
        return doc
    
    def _generate_fallback_project_overview(self, modules: Dict[str, ModuleInfo], project_name: str) -> str:
        """Generate fallback project overview."""
        doc = f"# {project_name}\n\n"
        doc += "Documentação do projeto gerada automaticamente.\n\n"
        doc += "## Estrutura do Projeto\n\n"
        
        for path, module in modules.items():
            file_name = Path(path).name
            doc += f"- **{file_name}**: {len(module.functions)} funções, {len(module.classes)} classes\n"
        
        return doc
    
    def _get_classification_context(self, classification: str) -> Dict[str, str]:
        """Get context and instructions specific to file classification."""
        contexts = {
            'controller': {
                'name': 'Controller (Controlador)',
                'description': 'Este arquivo é um Controller ASP.NET Core responsável por expor endpoints REST da API. Controllers gerenciam requisições HTTP, validam dados de entrada, orquestram operações de negócio e retornam respostas formatadas.',
                'instructions': '''
- Documente todos os endpoints HTTP (GET, POST, PUT, DELETE) com exemplos completos
- Descreva parâmetros de rota, query parameters e request bodies
- Explique códigos de status HTTP retornados
- Documente autenticação e autorização necessárias
- Inclua exemplos de requisições e respostas
- Explique middleware utilizado
- Documente validações de entrada
- Descreva tratamento de erros e exceções
'''
            },
            'service': {
                'name': 'Service (Serviço)',
                'description': 'Este arquivo implementa serviços de aplicação ou domínio, contendo lógica de negócio e operações específicas. Services coordenam entre diferentes componentes e implementam casos de uso complexos.',
                'instructions': '''
- Documente todas as operações de negócio implementadas
- Explique regras de negócio aplicadas
- Descreva dependências injetadas e sua finalidade
- Documente fluxos de dados entre componentes
- Inclua exemplos de uso dos métodos
- Explique tratamento de transações
- Documente validações e verificações
- Descreva padrões de retry e circuit breaker se aplicável
'''
            },
            'repository': {
                'name': 'Repository (Repositório)',
                'description': 'Este arquivo implementa o padrão Repository, fornecendo uma abstração para acesso a dados. Repositories encapsulam operações de persistência e consulta ao banco de dados.',
                'instructions': '''
- Documente todas as operações de acesso a dados
- Explique queries complexas e otimizações
- Descreva mapeamentos de entidades
- Documente índices e constraints utilizados
- Inclua exemplos de uso dos métodos
- Explique estratégias de cache se aplicável
- Documente performance e paginação
- Descreva tratamento de concorrência
'''
            },
            'entity': {
                'name': 'Entity (Entidade)',
                'description': 'Este arquivo define uma entidade do domínio, representando um objeto de negócio com identidade única. Entities encapsulam dados e comportamentos relacionados ao domínio.',
                'instructions': '''
- Documente todas as propriedades e sua finalidade
- Explique relacionamentos com outras entidades
- Descreva regras de negócio encapsuladas
- Documente validações e invariantes
- Inclua exemplos de criação e uso
- Explique navegação entre entidades
- Documente eventos de domínio se aplicável
- Descreva lifecycle da entidade
'''
            },
            'dto': {
                'name': 'DTO (Data Transfer Object)',
                'description': 'Este arquivo define objetos de transferência de dados, utilizados para transportar dados entre camadas da aplicação ou através de APIs. DTOs definem contratos de comunicação.',
                'instructions': '''
- Documente todas as propriedades e tipos
- Explique validações de dados aplicadas
- Descreva transformações entre DTOs e entidades
- Documente serialização e deserialização
- Inclua exemplos de uso em APIs
- Explique relacionamentos com outros DTOs
- Documente formatação e constraints
- Descreva versionamento se aplicável
'''
            },
            'configuration': {
                'name': 'Configuration (Configuração)',
                'description': 'Este arquivo contém configurações do Entity Framework, definindo mapeamentos entre entidades e tabelas do banco de dados. Configurations especificam schema, relacionamentos e constraints.',
                'instructions': '''
- Documente mapeamentos de propriedades
- Explique relacionamentos configurados
- Descreva índices e constraints
- Documente conversões de tipos
- Inclua exemplos de queries geradas
- Explique estratégias de loading
- Documente configurações de performance
- Descreva seeds e dados iniciais
'''
            },
            'handler': {
                'name': 'Handler (Manipulador)',
                'description': 'Este arquivo implementa handlers para comandos ou queries no padrão CQRS. Handlers processam requisições específicas e coordenam operações de negócio.',
                'instructions': '''
- Documente o comando ou query processado
- Explique fluxo de processamento
- Descreva validações aplicadas
- Documente side effects e eventos
- Inclua exemplos de uso
- Explique tratamento de erros
- Documente performance e otimizações
- Descreva integração com outros handlers
'''
            },
            'middleware': {
                'name': 'Middleware',
                'description': 'Este arquivo implementa middleware personalizado para o pipeline de requisições ASP.NET Core. Middlewares processam requisições HTTP de forma transversal.',
                'instructions': '''
- Documente funcionamento do middleware
- Explique posição no pipeline
- Descreva configuração necessária
- Documente impacto na performance
- Inclua exemplos de uso
- Explique tratamento de erros
- Documente logging e observabilidade
- Descreva casos de uso específicos
'''
            },
            'extension': {
                'name': 'Extension (Extensão)',
                'description': 'Este arquivo contém métodos de extensão que adicionam funcionalidades a tipos existentes. Extensions fornecem uma forma conveniente de estender comportamentos.',
                'instructions': '''
- Documente todos os métodos de extensão
- Explique tipos estendidos
- Descreva funcionalidades adicionadas
- Documente performance e limitations
- Inclua exemplos de uso
- Explique convenções seguidas
- Documente thread safety
- Descreva casos de uso recomendados
'''
            },
            'migration': {
                'name': 'Migration (Migração)',
                'description': 'Este arquivo contém uma migração do Entity Framework, definindo mudanças estruturais no banco de dados. Migrations permitem evolução controlada do schema.',
                'instructions': '''
- Documente mudanças no schema
- Explique impacto nos dados existentes
- Descreva estratégias de rollback
- Documente performance da migração
- Inclua scripts SQL gerados
- Explique dependências entre migrations
- Documente backup e recovery
- Descreva validações pós-migração
'''
            },
            'unknown': {
                'name': 'Arquivo Não Classificado',
                'description': 'Este arquivo não pôde ser classificado automaticamente. Pode conter utilitários, configurações ou funcionalidades específicas.',
                'instructions': '''
- Documente a finalidade do arquivo
- Explique funcionalidades implementadas
- Descreva como utilizar o código
- Documente dependências
- Inclua exemplos quando aplicável
- Explique contexto de uso
- Documente limitações conhecidas
- Descreva manutenção necessária
'''
            }
        }
        
        return contexts.get(classification, contexts['unknown'])
    
    def clear_cache(self):
        """Clear the documentation cache."""
        self.doc_cache.clear()
        logger.info("Documentation cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the documentation cache."""
        return {
            "cache_size": len(self.doc_cache),
            "cache_keys": list(self.doc_cache.keys())
        }