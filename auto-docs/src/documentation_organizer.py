"""
Documentation organizer module for auto-docs.

This module provides functionality to organize generated documentation
into structured folders and create navigation indices.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from analyzer import ModuleInfo
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DocumentationStructure:
    """Represents the structure of organized documentation."""
    base_path: str
    folders: Dict[str, List[str]]
    indices: Dict[str, str]
    navigation: Dict[str, List[Dict[str, str]]]


class DocumentationOrganizer:
    """Organizes documentation into structured folders and creates navigation."""
    
    def __init__(self, base_output_path: str, project_name: str):
        """
        Initialize the documentation organizer.
        
        Args:
            base_output_path: Base path for documentation output
            project_name: Name of the project being documented
        """
        self.base_path = Path(base_output_path)
        self.project_name = project_name
        
        # Define folder structure mapping
        self.folder_mapping = {
            'controller': 'api/controllers',
            'service': 'aplicacao/servicos',
            'repository': 'infraestrutura/repositorios',
            'entity': 'dominio/entidades',
            'dto': 'api/modelos',
            'configuration': 'infraestrutura/configuracoes',
            'handler': 'aplicacao/handlers',
            'middleware': 'api/middlewares',
            'extension': 'shared/extensoes',
            'migration': 'infraestrutura/migrations',
            'event': 'dominio/eventos',
            'value_object': 'dominio/objetos-valor',
            'command': 'aplicacao/comandos',
            'query': 'aplicacao/consultas',
            'validator': 'aplicacao/validadores',
            'exception': 'shared/excecoes',
            'utility': 'shared/utilitarios',
            'interface': 'shared/interfaces',
            'abstraction': 'shared/abstracoes',
            'builder': 'shared/builders',
            'db_context': 'infraestrutura/contextos',
            'unknown': 'outros'
        }
        
        # Create base structure
        self._create_base_structure()
    
    def _create_base_structure(self) -> None:
        """Create the base folder structure."""
        # Create main documentation folder
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Create all classified folders
        for folder_path in self.folder_mapping.values():
            full_path = self.base_path / folder_path
            full_path.mkdir(parents=True, exist_ok=True)
        
        # Create additional structural folders
        additional_folders = [
            'arquitetura',
            'deployment',
            'testes',
            'assets/diagrams',
            'assets/images'
        ]
        
        for folder in additional_folders:
            full_path = self.base_path / folder
            full_path.mkdir(parents=True, exist_ok=True)
    
    def organize_documentation(self, modules: Dict[str, ModuleInfo], 
                             documentation: Dict[str, str]) -> DocumentationStructure:
        """
        Organize documentation into structured folders.
        
        Args:
            modules: Dictionary of analyzed modules
            documentation: Dictionary of generated documentation
            
        Returns:
            DocumentationStructure with organized files
        """
        organized_structure = DocumentationStructure(
            base_path=str(self.base_path),
            folders={},
            indices={},
            navigation={}
        )
        
        # Organize files by classification
        for file_path, module_info in modules.items():
            if file_path not in documentation:
                continue
                
            classification = getattr(module_info, 'classification', 'unknown')
            folder_path = self.folder_mapping.get(classification, 'outros')
            
            # Create documentation file
            doc_filename = self._get_documentation_filename(file_path, module_info)
            doc_path = self.base_path / folder_path / doc_filename
            
            # Write documentation to file
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(documentation[file_path])
            
            # Track in structure
            if folder_path not in organized_structure.folders:
                organized_structure.folders[folder_path] = []
            organized_structure.folders[folder_path].append(doc_filename)
        
        # Create indices for each folder
        self._create_folder_indices(organized_structure, modules)
        
        # Create main navigation
        self._create_main_navigation(organized_structure)
        
        # Create main README
        self._create_main_readme(organized_structure, modules)
        
        return organized_structure
    
    def _get_documentation_filename(self, file_path: str, module_info: ModuleInfo) -> str:
        """Generate appropriate filename for documentation."""
        original_name = Path(file_path).stem
        
        # Add classification prefix for better organization
        classification = getattr(module_info, 'classification', 'unknown')
        
        # Special handling for different classifications
        if classification == 'controller':
            return f"{original_name}.md"
        elif classification == 'entity':
            return f"{original_name}.md"
        elif classification == 'service':
            return f"{original_name}.md"
        elif classification == 'repository':
            return f"{original_name}.md"
        else:
            return f"{original_name}.md"
    
    def _create_folder_indices(self, structure: DocumentationStructure, 
                              modules: Dict[str, ModuleInfo]) -> None:
        """Create index files for each folder."""
        for folder_path, files in structure.folders.items():
            if not files:
                continue
                
            # Group files by classification
            classification = self._get_classification_from_folder(folder_path)
            index_content = self._generate_folder_index(folder_path, files, classification, modules)
            
            # Write index file
            index_path = self.base_path / folder_path / "README.md"
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)
            
            structure.indices[folder_path] = str(index_path)
    
    def _get_classification_from_folder(self, folder_path: str) -> str:
        """Get classification type from folder path."""
        for classification, path in self.folder_mapping.items():
            if path == folder_path:
                return classification
        return 'unknown'
    
    def _generate_folder_index(self, folder_path: str, files: List[str], 
                             classification: str, modules: Dict[str, ModuleInfo]) -> str:
        """Generate index content for a folder."""
        folder_name = folder_path.split('/')[-1].title()
        classification_names = {
            'controller': 'Controllers',
            'service': 'Serviços',
            'repository': 'Repositórios',
            'entity': 'Entidades',
            'dto': 'Modelos de Dados',
            'configuration': 'Configurações',
            'handler': 'Handlers',
            'middleware': 'Middlewares',
            'extension': 'Extensões',
            'migration': 'Migrações',
            'event': 'Eventos',
            'value_object': 'Objetos de Valor',
            'command': 'Comandos',
            'query': 'Consultas',
            'validator': 'Validadores',
            'exception': 'Exceções',
            'utility': 'Utilitários',
            'interface': 'Interfaces',
            'abstraction': 'Abstrações',
            'builder': 'Builders',
            'db_context': 'Contextos de Banco',
            'unknown': 'Outros'
        }
        
        section_name = classification_names.get(classification, folder_name)
        
        content = f"""# {section_name}

## Visão Geral

Esta seção contém a documentação de todos os {section_name.lower()} do projeto {self.project_name}.

## Arquivos Documentados

| Arquivo | Descrição | Namespace |
|---------|-----------|-----------|
"""
        
        # Add file entries
        for file in sorted(files):
            file_stem = Path(file).stem
            
            # Find corresponding module info
            module_info = None
            for path, info in modules.items():
                if Path(path).stem == file_stem:
                    module_info = info
                    break
            
            description = "Documentação não disponível"
            namespace = "N/A"
            
            if module_info:
                description = module_info.docstring or "Sem descrição"
                namespace = module_info.namespace or "N/A"
                # Truncate description if too long
                if len(description) > 80:
                    description = description[:77] + "..."
            
            content += f"| [{file_stem}](./{file}) | {description} | {namespace} |\n"
        
        content += f"""

## Navegação

- [← Voltar ao Índice Principal](../../README.md)
- [📁 Ver Estrutura Completa](../../arquitetura/estrutura-projeto.md)

## Estatísticas

- **Total de arquivos**: {len(files)}
- **Última atualização**: {datetime.now().strftime('%d/%m/%Y %H:%M')}

---
*Documentação gerada automaticamente pelo auto-docs*
"""
        
        return content
    
    def _create_main_navigation(self, structure: DocumentationStructure) -> None:
        """Create main navigation structure."""
        navigation_content = self._generate_navigation_content(structure)
        
        # Write navigation file
        nav_path = self.base_path / "NAVIGATION.md"
        with open(nav_path, 'w', encoding='utf-8') as f:
            f.write(navigation_content)
        
        structure.navigation['main'] = str(nav_path)
    
    def _generate_navigation_content(self, structure: DocumentationStructure) -> str:
        """Generate navigation content."""
        content = f"""# Navegação - {self.project_name}

## Estrutura da Documentação

### 🏗️ Arquitetura
- [Visão Geral da Arquitetura](arquitetura/clean-architecture.md)
- [Dependências do Projeto](arquitetura/dependencias.md)
- [Padrões Utilizados](arquitetura/padroes-utilizados.md)
- [Estrutura do Projeto](arquitetura/estrutura-projeto.md)

### 🌐 API (Camada de Apresentação)
"""
        
        # Add API sections
        api_sections = [
            ('api/controllers', 'Controllers'),
            ('api/middlewares', 'Middlewares'),
            ('api/modelos', 'Modelos de Dados')
        ]
        
        for folder_path, section_name in api_sections:
            if folder_path in structure.folders:
                content += f"- [{section_name}]({folder_path}/README.md)\n"
        
        content += """
### 🎯 Aplicação (Camada de Negócio)
"""
        
        # Add application sections
        app_sections = [
            ('aplicacao/servicos', 'Serviços'),
            ('aplicacao/handlers', 'Handlers'),
            ('aplicacao/comandos', 'Comandos'),
            ('aplicacao/consultas', 'Consultas'),
            ('aplicacao/validadores', 'Validadores')
        ]
        
        for folder_path, section_name in app_sections:
            if folder_path in structure.folders:
                content += f"- [{section_name}]({folder_path}/README.md)\n"
        
        content += """
### 🏛️ Domínio (Camada de Negócio)
"""
        
        # Add domain sections
        domain_sections = [
            ('dominio/entidades', 'Entidades'),
            ('dominio/eventos', 'Eventos'),
            ('dominio/objetos-valor', 'Objetos de Valor')
        ]
        
        for folder_path, section_name in domain_sections:
            if folder_path in structure.folders:
                content += f"- [{section_name}]({folder_path}/README.md)\n"
        
        content += """
### 🔧 Infraestrutura (Camada de Dados)
"""
        
        # Add infrastructure sections
        infra_sections = [
            ('infraestrutura/repositorios', 'Repositórios'),
            ('infraestrutura/configuracoes', 'Configurações'),
            ('infraestrutura/migrations', 'Migrações'),
            ('infraestrutura/contextos', 'Contextos de Banco')
        ]
        
        for folder_path, section_name in infra_sections:
            if folder_path in structure.folders:
                content += f"- [{section_name}]({folder_path}/README.md)\n"
        
        content += """
### 🔄 Compartilhado
"""
        
        # Add shared sections
        shared_sections = [
            ('shared/extensoes', 'Extensões'),
            ('shared/excecoes', 'Exceções'),
            ('shared/utilitarios', 'Utilitários'),
            ('shared/interfaces', 'Interfaces')
        ]
        
        for folder_path, section_name in shared_sections:
            if folder_path in structure.folders:
                content += f"- [{section_name}]({folder_path}/README.md)\n"
        
        content += f"""
### 📚 Outros
- [Deployment](deployment/README.md)
- [Testes](testes/README.md)
- [Assets](assets/README.md)

## Estatísticas do Projeto

- **Total de pastas**: {len(structure.folders)}
- **Total de arquivos documentados**: {sum(len(files) for files in structure.folders.values())}
- **Última atualização**: {datetime.now().strftime('%d/%m/%Y %H:%M')}

---
*Documentação gerada automaticamente pelo auto-docs*
"""
        
        return content
    
    def _create_main_readme(self, structure: DocumentationStructure, 
                           modules: Dict[str, ModuleInfo]) -> None:
        """Create main README file."""
        readme_content = self._generate_main_readme_content(structure, modules)
        
        # Write main README
        readme_path = self.base_path / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
    
    def _generate_main_readme_content(self, structure: DocumentationStructure, 
                                    modules: Dict[str, ModuleInfo]) -> str:
        """Generate main README content."""
        total_files = sum(len(files) for files in structure.folders.values())
        
        content = f"""# {self.project_name} - Documentação Técnica

## 📋 Índice

- [🧭 Navegação Completa](NAVIGATION.md)
- [🏗️ Arquitetura](arquitetura/README.md)
- [🚀 Início Rápido](#inicio-rapido)
- [📁 Estrutura](#estrutura)
- [📊 Estatísticas](#estatisticas)

## 🧭 Navegação Rápida

### Por Tipo de Componente

| Componente | Quantidade | Descrição |
|------------|------------|-----------|
"""
        
        # Add component statistics
        classification_counts = {}
        for module_info in modules.values():
            classification = getattr(module_info, 'classification', 'unknown')
            classification_counts[classification] = classification_counts.get(classification, 0) + 1
        
        classification_descriptions = {
            'controller': 'Endpoints da API REST',
            'service': 'Lógica de negócio',
            'repository': 'Acesso a dados',
            'entity': 'Entidades do domínio',
            'dto': 'Objetos de transferência',
            'configuration': 'Configurações EF',
            'handler': 'Handlers CQRS',
            'middleware': 'Middlewares HTTP',
            'extension': 'Métodos de extensão',
            'migration': 'Migrações de banco',
            'event': 'Eventos de domínio',
            'value_object': 'Objetos de valor',
            'command': 'Comandos CQRS',
            'query': 'Consultas CQRS',
            'validator': 'Validadores',
            'exception': 'Exceções customizadas',
            'utility': 'Utilitários',
            'interface': 'Interfaces',
            'abstraction': 'Abstrações',
            'builder': 'Builders',
            'db_context': 'Contextos de banco',
            'unknown': 'Não classificados'
        }
        
        for classification, count in sorted(classification_counts.items()):
            folder_path = self.folder_mapping.get(classification, 'outros')
            description = classification_descriptions.get(classification, 'Componentes diversos')
            content += f"| [{classification.title()}]({folder_path}/README.md) | {count} | {description} |\n"
        
        content += f"""

## 🚀 Início Rápido

### 1. Estrutura da Documentação

A documentação está organizada seguindo a arquitetura limpa do projeto:

```
docs/
├── 🌐 api/                 # Camada de Apresentação
│   ├── controllers/        # Controllers da API
│   ├── middlewares/        # Middlewares HTTP
│   └── modelos/           # DTOs e ViewModels
├── 🎯 aplicacao/          # Camada de Aplicação
│   ├── servicos/          # Serviços de aplicação
│   ├── handlers/          # Handlers CQRS
│   ├── comandos/          # Commands
│   └── consultas/         # Queries
├── 🏛️ dominio/            # Camada de Domínio
│   ├── entidades/         # Entidades
│   ├── eventos/           # Domain Events
│   └── objetos-valor/     # Value Objects
├── 🔧 infraestrutura/     # Camada de Infraestrutura
│   ├── repositorios/      # Repositórios
│   ├── configuracoes/     # Configurações EF
│   └── migrations/        # Migrações
└── 🔄 shared/             # Componentes Compartilhados
    ├── extensoes/         # Extensions
    ├── utilitarios/       # Utilities
    └── interfaces/        # Interfaces
```

### 2. Como Navegar

1. **Visão Geral**: Comece pelo [README principal](README.md)
2. **Navegação**: Use o [guia de navegação](NAVIGATION.md)
3. **Arquitetura**: Entenda a [arquitetura do sistema](arquitetura/README.md)
4. **Componentes**: Explore os componentes por categoria

### 3. Busca Rápida

- **Controllers**: [`api/controllers/`](api/controllers/README.md)
- **Entidades**: [`dominio/entidades/`](dominio/entidades/README.md)
- **Repositórios**: [`infraestrutura/repositorios/`](infraestrutura/repositorios/README.md)
- **Serviços**: [`aplicacao/servicos/`](aplicacao/servicos/README.md)

## 📁 Estrutura

### Camadas da Aplicação

1. **🌐 API (Apresentação)**
   - Exposição de endpoints REST
   - Middlewares e filtros
   - Validação de entrada
   - Formatação de resposta

2. **🎯 Aplicação (Casos de Uso)**
   - Orquestração de operações
   - Lógica de aplicação
   - Handlers CQRS
   - Validação de negócio

3. **🏛️ Domínio (Negócio)**
   - Entidades e agregados
   - Regras de negócio
   - Eventos de domínio
   - Objetos de valor

4. **🔧 Infraestrutura (Dados)**
   - Acesso a dados
   - Integrações externas
   - Configurações
   - Migrações

## 📊 Estatísticas

- **Total de arquivos documentados**: {total_files}
- **Namespaces únicos**: {len(set(m.namespace for m in modules.values() if m.namespace))}
- **Classificações**: {len(classification_counts)}
- **Última atualização**: {datetime.now().strftime('%d/%m/%Y %H:%M')}

### Distribuição por Tipo

```
{chr(10).join(f"{k}: {v}" for k, v in sorted(classification_counts.items(), key=lambda x: x[1], reverse=True))}
```

## 🤝 Contribuindo

Para contribuir com a documentação:

1. Mantenha o padrão de organização
2. Siga as convenções de nomenclatura
3. Atualize os índices quando necessário
4. Valide a documentação gerada

## 📞 Suporte

- **Documentação**: Consulte os arquivos específicos
- **Código**: Veja o código-fonte correspondente
- **Dúvidas**: Abra uma issue no projeto

---

*Documentação gerada automaticamente pelo auto-docs em {datetime.now().strftime('%d/%m/%Y %H:%M')}*
"""
        
        return content
    
    def create_architecture_docs(self, modules: Dict[str, ModuleInfo]) -> None:
        """Create architecture documentation files."""
        arch_path = self.base_path / "arquitetura"
        
        # Create architecture overview
        self._create_architecture_overview(arch_path, modules)
        
        # Create dependencies documentation
        self._create_dependencies_doc(arch_path, modules)
        
        # Create patterns documentation
        self._create_patterns_doc(arch_path, modules)
        
        # Create project structure documentation
        self._create_project_structure_doc(arch_path, modules)
    
    def _create_architecture_overview(self, arch_path: Path, modules: Dict[str, ModuleInfo]) -> None:
        """Create architecture overview documentation."""
        content = f"""# Arquitetura - {self.project_name}

## Visão Geral

O {self.project_name} segue os princípios da **Clean Architecture** (Arquitetura Limpa), promovendo separação de responsabilidades e baixo acoplamento entre as camadas.

## Camadas da Arquitetura

### 1. 🌐 Camada de Apresentação (API)
- **Responsabilidade**: Interface com o mundo externo
- **Componentes**: Controllers, Middlewares, DTOs
- **Tecnologias**: ASP.NET Core, JWT, Swagger

### 2. 🎯 Camada de Aplicação
- **Responsabilidade**: Orquestração de casos de uso
- **Componentes**: Services, Handlers, Commands, Queries
- **Padrões**: CQRS, Mediator, Repository

### 3. 🏛️ Camada de Domínio
- **Responsabilidade**: Regras de negócio e entidades
- **Componentes**: Entities, Value Objects, Domain Events
- **Padrões**: DDD, Domain Events, Aggregate Root

### 4. 🔧 Camada de Infraestrutura
- **Responsabilidade**: Acesso a dados e integrações
- **Componentes**: Repositories, Configurations, Migrations
- **Tecnologias**: Entity Framework, PostgreSQL, Redis

## Fluxo de Dados

```
[HTTP Request] → [Controller] → [Handler] → [Service] → [Repository] → [Database]
                      ↓              ↓           ↓
                   [Middleware]   [Domain]   [Entity]
```

## Princípios Aplicados

### SOLID
- **S**ingle Responsibility Principle
- **O**pen/Closed Principle
- **L**iskov Substitution Principle
- **I**nterface Segregation Principle
- **D**ependency Inversion Principle

### DDD (Domain-Driven Design)
- Entities com comportamento
- Value Objects imutáveis
- Aggregates bem definidos
- Domain Events para comunicação

### CQRS (Command Query Responsibility Segregation)
- Commands para operações de escrita
- Queries para operações de leitura
- Handlers especializados
- Separação de responsabilidades

## Dependências

### Inversão de Dependências
```
Application → Domain ← Infrastructure
     ↑                      ↑
   API ←→ Shared ←→ Infrastructure
```

### Principais Abstrações
- `IRepository<T>`: Acesso a dados
- `IUnitOfWork`: Gerenciamento de transações
- `IMediator`: Comunicação entre camadas
- `IMapper`: Mapeamento de objetos

## Qualidade e Testes

### Estratégias de Teste
- **Unit Tests**: Camada de domínio
- **Integration Tests**: Repositórios
- **API Tests**: Controllers
- **E2E Tests**: Fluxos completos

### Cobertura de Testes
- Domínio: 90%+
- Aplicação: 80%+
- API: 70%+
- Infraestrutura: 60%+

## Monitoramento

### Observabilidade
- **Logs**: Serilog estruturado
- **Métricas**: Application Insights
- **Tracing**: OpenTelemetry
- **Health Checks**: ASP.NET Core

### Performance
- **Caching**: Redis
- **Database**: Índices otimizados
- **API**: Rate limiting
- **Background**: Hangfire

---
*Documentação gerada automaticamente pelo auto-docs*
"""
        
        with open(arch_path / "clean-architecture.md", 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _create_dependencies_doc(self, arch_path: Path, modules: Dict[str, ModuleInfo]) -> None:
        """Create dependencies documentation."""
        # Extract unique namespaces and their relationships
        namespaces = set()
        using_relationships = {}
        
        for module_info in modules.values():
            if module_info.namespace:
                namespaces.add(module_info.namespace)
                using_relationships[module_info.namespace] = module_info.imports
        
        content = f"""# Dependências - {self.project_name}

## Mapa de Dependências

### Namespaces do Projeto
{chr(10).join(f"- `{ns}`" for ns in sorted(namespaces))}

### Dependências Externas Principais

#### Microsoft Packages
- `Microsoft.AspNetCore.App`: Framework web
- `Microsoft.EntityFrameworkCore`: ORM
- `Microsoft.AspNetCore.Authentication.JwtBearer`: JWT
- `Microsoft.Extensions.DependencyInjection`: DI Container

#### Third-Party Packages
- `AutoMapper`: Mapeamento de objetos
- `MediatR`: Mediator pattern
- `FluentValidation`: Validação
- `Serilog`: Logging
- `Hangfire`: Background jobs
- `Npgsql`: PostgreSQL driver

### Análise de Dependências

#### Camada API
- Depende de: Application, Shared
- Não depende de: Domain, Infrastructure (diretamente)

#### Camada Application
- Depende de: Domain, Shared
- Não depende de: Infrastructure, API

#### Camada Domain
- Depende de: Apenas .NET Standard
- Não depende de: Nenhuma outra camada

#### Camada Infrastructure
- Depende de: Domain, Application
- Implementa: Abstrações das outras camadas

## Diagrama de Dependências

```mermaid
graph TD
    API[API Layer]
    APP[Application Layer]
    DOM[Domain Layer]
    INF[Infrastructure Layer]
    SHR[Shared Layer]
    
    API --> APP
    API --> SHR
    APP --> DOM
    APP --> SHR
    INF --> DOM
    INF --> APP
    INF --> SHR
```

## Gestão de Dependências

### NuGet Packages
- Versionamento semântico
- Atualizações controladas
- Auditoria de segurança
- Dependências transitivas

### Injeção de Dependências
- Container nativo do .NET
- Scoped services
- Singleton services
- Transient services

---
*Documentação gerada automaticamente pelo auto-docs*
"""
        
        with open(arch_path / "dependencias.md", 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _create_patterns_doc(self, arch_path: Path, modules: Dict[str, ModuleInfo]) -> None:
        """Create patterns documentation."""
        content = f"""# Padrões de Design - {self.project_name}

## Padrões Arquiteturais

### 1. Clean Architecture
- **Finalidade**: Separação de responsabilidades
- **Implementação**: Camadas bem definidas
- **Benefícios**: Testabilidade, manutenibilidade
- **Localização**: Estrutura geral do projeto

### 2. CQRS (Command Query Responsibility Segregation)
- **Finalidade**: Separar operações de leitura e escrita
- **Implementação**: Commands e Queries separados
- **Benefícios**: Performance, escalabilidade
- **Localização**: Application layer

### 3. Domain-Driven Design (DDD)
- **Finalidade**: Modelagem rica do domínio
- **Implementação**: Entities, Value Objects, Aggregates
- **Benefícios**: Expressividade, alinhamento com negócio
- **Localização**: Domain layer

## Padrões de Implementação

### 1. Repository Pattern
- **Finalidade**: Abstração de acesso a dados
- **Implementação**: Interfaces e implementações
- **Benefícios**: Testabilidade, flexibilidade
- **Localização**: Infrastructure layer

### 2. Unit of Work
- **Finalidade**: Gerenciamento de transações
- **Implementação**: Context único por operação
- **Benefícios**: Consistência, performance
- **Localização**: Infrastructure layer

### 3. Mediator Pattern
- **Finalidade**: Desacoplamento entre componentes
- **Implementação**: MediatR library
- **Benefícios**: Baixo acoplamento, organização
- **Localização**: Application layer

### 4. Factory Pattern
- **Finalidade**: Criação de objetos complexos
- **Implementação**: Factory classes
- **Benefícios**: Flexibilidade, reutilização
- **Localização**: Shared layer

## Padrões de Comunicação

### 1. Request/Response
- **Finalidade**: Comunicação síncrona
- **Implementação**: DTOs e ViewModels
- **Benefícios**: Simplicidade, clareza
- **Localização**: API layer

### 2. Domain Events
- **Finalidade**: Comunicação assíncrona interna
- **Implementação**: Event handlers
- **Benefícios**: Desacoplamento, extensibilidade
- **Localização**: Domain layer

### 3. Integration Events
- **Finalidade**: Comunicação entre bounded contexts
- **Implementação**: Message brokers
- **Benefícios**: Escalabilidade, resiliência
- **Localização**: Infrastructure layer

## Padrões de Dados

### 1. Active Record vs Data Mapper
- **Escolha**: Data Mapper (Entity Framework)
- **Justificativa**: Separação de responsabilidades
- **Implementação**: Entities + Configurations
- **Benefícios**: Testabilidade, flexibilidade

### 2. Query Object
- **Finalidade**: Encapsulamento de consultas complexas
- **Implementação**: Query classes
- **Benefícios**: Reutilização, testabilidade
- **Localização**: Application layer

### 3. Specification Pattern
- **Finalidade**: Critérios de consulta reutilizáveis
- **Implementação**: Specification classes
- **Benefícios**: Composabilidade, testabilidade
- **Localização**: Domain layer

## Padrões de Validação

### 1. Fluent Validation
- **Finalidade**: Validação expressiva
- **Implementação**: FluentValidation library
- **Benefícios**: Clareza, reutilização
- **Localização**: Application layer

### 2. Guard Clauses
- **Finalidade**: Validação de pré-condições
- **Implementação**: Guard methods
- **Benefícios**: Robustez, clareza
- **Localização**: Domain layer

## Padrões de Tratamento de Erros

### 1. Result Pattern
- **Finalidade**: Tratamento explícito de erros
- **Implementação**: Result<T> classes
- **Benefícios**: Clareza, robustez
- **Localização**: Application layer

### 2. Exception Handling
- **Finalidade**: Tratamento centralizado
- **Implementação**: Global exception handler
- **Benefícios**: Consistência, monitoramento
- **Localização**: API layer

## Convenções de Nomenclatura

### Classes
- **Controllers**: `[Entity]Controller`
- **Services**: `[Entity]Service`
- **Repositories**: `[Entity]Repository`
- **Entities**: `[EntityName]`
- **DTOs**: `[Entity][Action]Request/Response`

### Métodos
- **Commands**: `Create`, `Update`, `Delete`
- **Queries**: `Get`, `List`, `Find`
- **Handlers**: `Handle`
- **Validations**: `Validate`

### Propriedades
- **Entities**: PascalCase
- **DTOs**: PascalCase
- **Constants**: UPPER_CASE
- **Private fields**: _camelCase

---
*Documentação gerada automaticamente pelo auto-docs*
"""
        
        with open(arch_path / "padroes-utilizados.md", 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _create_project_structure_doc(self, arch_path: Path, modules: Dict[str, ModuleInfo]) -> None:
        """Create project structure documentation."""
        content = f"""# Estrutura do Projeto - {self.project_name}

## Estrutura de Pastas

```
src/
├── Receba.Api/                 # 🌐 Camada de Apresentação
│   ├── Controllers/            # Controllers da API REST
│   ├── Middlewares/            # Middlewares personalizados
│   ├── Configuration/          # Configurações de inicialização
│   ├── Extensions/             # Extensões de configuração
│   ├── Views/                  # DTOs e ViewModels
│   ├── Mappers/                # Mapeamentos AutoMapper
│   ├── Utils/                  # Utilitários da API
│   └── Program.cs              # Ponto de entrada
├── Receba.Core/                # 🎯 Camada de Aplicação + Domínio
│   ├── Application/            # Casos de uso e handlers
│   │   ├── Commands/           # Comandos CQRS
│   │   ├── Queries/            # Consultas CQRS
│   │   ├── Handlers/           # Handlers MediatR
│   │   └── Services/           # Serviços de aplicação
│   ├── Domain/                 # Domínio do negócio
│   │   ├── Entities/           # Entidades de domínio
│   │   ├── ValueObjects/       # Objetos de valor
│   │   ├── Events/             # Eventos de domínio
│   │   └── Interfaces/         # Contratos do domínio
│   ├── Exceptions/             # Exceções customizadas
│   ├── Validators/             # Validadores FluentValidation
│   └── Resources/              # Recursos de localização
├── Receba.Infrastructure/      # 🔧 Camada de Infraestrutura
│   ├── Repository/             # Implementações de repositório
│   ├── Configurations/         # Configurações Entity Framework
│   ├── Migrations/             # Migrações do banco
│   ├── Service/                # Serviços de infraestrutura
│   └── RecebaContext.cs        # Contexto do EF Core
└── Receba.Shared/              # 🔄 Componentes Compartilhados
    ├── Extensions/             # Métodos de extensão
    ├── Helpers/                # Utilitários auxiliares
    └── Common/                 # Componentes comuns
```

## Distribuição de Arquivos

### Por Camada
- **API**: {len([m for m in modules.values() if 'Api' in m.file_path])} arquivos
- **Core**: {len([m for m in modules.values() if 'Core' in m.file_path])} arquivos
- **Infrastructure**: {len([m for m in modules.values() if 'Infrastructure' in m.file_path])} arquivos
- **Shared**: {len([m for m in modules.values() if 'Shared' in m.file_path])} arquivos

### Por Tipo de Componente
"""
        
        # Add component counts
        classification_counts = {}
        for module_info in modules.values():
            classification = getattr(module_info, 'classification', 'unknown')
            classification_counts[classification] = classification_counts.get(classification, 0) + 1
        
        for classification, count in sorted(classification_counts.items()):
            content += f"- **{classification.title()}**: {count} arquivos\n"
        
        content += f"""

## Namespaces Principais

### Receba.Api
- `Receba.Api.Controllers`: Controllers da API
- `Receba.Api.Middlewares`: Middlewares HTTP
- `Receba.Api.Configuration`: Configurações de startup
- `Receba.Api.Extensions`: Extensões de configuração

### Receba.Core
- `Receba.Core.Domain.Entities`: Entidades de domínio
- `Receba.Core.Application.Commands`: Comandos CQRS
- `Receba.Core.Application.Queries`: Consultas CQRS
- `Receba.Core.Application.Handlers`: Handlers MediatR

### Receba.Infrastructure
- `Receba.Infrastructure.Repository`: Repositórios
- `Receba.Infrastructure.Configurations`: Configurações EF
- `Receba.Infrastructure.Service`: Serviços de infraestrutura
- `Receba.Infrastructure.Migrations`: Migrações

### Receba.Shared
- `Receba.Shared.Extensions`: Métodos de extensão
- `Receba.Shared.Helpers`: Utilitários auxiliares
- `Receba.Shared.Common`: Componentes comuns

## Convenções de Organização

### Nomenclatura de Arquivos
- **Controllers**: `[Entity]Controller.cs`
- **Services**: `[Entity]Service.cs`
- **Repositories**: `[Entity]Repository.cs`
- **Entities**: `[EntityName].cs`
- **DTOs**: `[Entity][Action]Request.cs` / `[Entity][Action]Response.cs`

### Estrutura de Pastas
- Uma pasta por contexto/agregado
- Separação por tipo de componente
- Agrupamento por funcionalidade
- Hierarquia clara e intuitiva

### Dependências entre Camadas
```
API → Application → Domain
         ↓
Infrastructure → Domain
```

## Configuração do Projeto

### Arquivos de Configuração
- `appsettings.json`: Configurações base
- `appsettings.Development.json`: Configurações de desenvolvimento
- `appsettings.Production.json`: Configurações de produção
- `Program.cs`: Configuração de inicialização

### Variáveis de Ambiente
- `ASPNETCORE_ENVIRONMENT`: Ambiente de execução
- `ConnectionStrings__DefaultConnection`: String de conexão
- `JWT__Secret`: Chave secreta para JWT
- `Logging__LogLevel__Default`: Nível de log

## Estrutura de Dados

### Entidades Principais
{chr(10).join(f"- `{Path(m.file_path).stem}`" for m in modules.values() if getattr(m, 'classification', None) == 'entity')[:10]}

### Repositórios
{chr(10).join(f"- `{Path(m.file_path).stem}`" for m in modules.values() if getattr(m, 'classification', None) == 'repository')[:10]}

### Controllers
{chr(10).join(f"- `{Path(m.file_path).stem}`" for m in modules.values() if getattr(m, 'classification', None) == 'controller')[:10]}

## Manutenção e Evolução

### Adicionando Novos Componentes
1. Identifique a camada apropriada
2. Siga as convenções de nomenclatura
3. Implemente as interfaces necessárias
4. Adicione testes adequados
5. Atualize a documentação

### Refatoração
- Mantenha a separação de responsabilidades
- Preserve as interfaces públicas
- Atualize testes e documentação
- Valide a integridade das dependências

---
*Documentação gerada automaticamente pelo auto-docs*
"""
        
        with open(arch_path / "estrutura-projeto.md", 'w', encoding='utf-8') as f:
            f.write(content)