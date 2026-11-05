# 01 — Engenharia Reversa

## 1. Objetivo

Este documento registra o estado atual do projeto **Análise de Consumo de Mercado**, antes da evolução para uma arquitetura de Engenharia de Dados.

O objetivo da engenharia reversa é entender:

* como os dados são obtidos;
* como são armazenados;
* qual é a granularidade dos dados;
* quais transformações são realizadas;
* quais regras de negócio existem;
* quais limitações existem na arquitetura atual;
* quais pontos deverão ser evoluídos nas próximas versões.

Este documento representa a **V1 — estado atual do projeto**.

---

## 2. Contexto do projeto

O projeto foi inicialmente desenvolvido para registrar e analisar gastos com compras de supermercado.

Os dados são utilizados para gerar análises e indicadores relacionados a:

* gastos ao longo do tempo;
* produtos consumidos;
* categorias de produtos;
* frequência de compras;
* preços;
* quantidade;
* comportamento de consumo;
* análise de Pareto;
* evolução dos gastos.

A camada de visualização atual é construída no **Power BI**.

---

## 3. Fonte dos dados

### 3.1 Fonte principal atual

A fonte principal é uma planilha **Excel**, que acumula os registros históricos de compras.

Também existe a possibilidade de utilização de arquivos **CSV**.

### 3.2 Origem dos dados

Os dados são obtidos a partir dos cupons/notas fiscais das compras.

Atualmente, a captura dos dados ainda não é automatizada.

O processo utilizado é:

1. O cupom fiscal é fotografado ou disponibilizado;
2. Os dados do cupom são extraídos manualmente/assistidos por OCR ou IA;
3. Os dados extraídos são revisados;
4. Os registros são copiados para a planilha Excel;
5. O Power BI utiliza a planilha como fonte para as análises.

Nem todas as compras possuem atualmente a imagem original do cupom fiscal.

---

## 4. Fluxo atual dos dados

A arquitetura atual pode ser representada da seguinte forma:

```text
Cupom / Nota Fiscal
        │
        ▼
Extração manual / assistida
        │
        ▼
      Excel
        │
        ▼
   Power Query
        │
        ▼
    Power BI
        │
        ▼
    Dashboard
```

### Responsabilidades atuais

| Componente         | Responsabilidade                            |
| ------------------ | ------------------------------------------- |
| Cupom fiscal       | Fonte original das informações              |
| Extração manual/IA | Captura das informações do cupom            |
| Excel              | Armazenamento dos dados estruturados        |
| Power Query        | Limpeza e transformação                     |
| Power BI           | Modelagem, medidas, análises e visualização |

---

## 5. Estrutura atual dos dados

A tabela principal possui atualmente campos semelhantes aos seguintes:

| Campo                | Descrição                              |
| -------------------- | -------------------------------------- |
| Descrição do Produto | Descrição original do produto no cupom |
| Categoria            | Categoria atribuída ao produto         |
| Qtde                 | Quantidade comprada                    |
| Unid                 | Unidade de medida                      |
| Vlr Unit (R$)        | Valor unitário                         |
| Tot (R$)             | Valor total do item                    |
| Data Compra          | Data da compra                         |
| Dia de Semana        | Dia da semana derivado da data         |

---

## 6. Granularidade

A granularidade atual da tabela é:

> **1 linha representa 1 item/produto comprado.**

Exemplo:

```text
BANANA BRANCA KG
Quantidade: 0,755 KG
Valor unitário: R$ 6,49
Valor total: R$ 4,90
Data: 09/03/2026
```

Portanto, a tabela atual representa **itens de compra**, e não necessariamente uma compra completa.

---

## 7. Identificação de uma compra

Atualmente não existe um identificador confiável para cada compra/cupom, como:

```text
id_compra
id_cupom
id_nota
```

A data da compra está disponível, porém **não deve ser utilizada como identificador da compra**, pois podem existir múltiplas compras no mesmo dia.

Exemplo:

```text
25/03/2026 → compra A
25/03/2026 → compra B
```

Sem uma informação adicional, não é possível determinar automaticamente quais itens pertencem a cada compra.

### Situação atual

Para parte do histórico:

```text
id_compra = desconhecido
```

### Situação futura

Para novas compras capturadas automaticamente, o sistema deverá gerar um identificador único para cada cupom/compra.

---

## 8. Problemas identificados nos dados

### 8.1 Descrições inconsistentes

O mesmo produto pode aparecer com pequenas diferenças de formatação.

Exemplos:

```text
AGRIAO   HIDROPONICO DEVILE UN
AGRIAO HIDROPONICO DEVILE UN
```

ou:

```text
BANANA BRANCA KG
BANANA   BRANCA KG
```

Essas diferenças podem fazer com que o mesmo produto seja interpretado como produtos diferentes.

---

### 8.2 Produtos promocionais

Existem descrições como:

```text
BANANA BRANCA KG PROMOCAO
```

Enquanto outras ocorrências aparecem como:

```text
BANANA BRANCA KG
```

Para fins analíticos, pode ser necessário distinguir:

```text
produto_original
```

de:

```text
produto_padronizado
```

A descrição original deve ser preservada.

---

### 8.3 Valores monetários

Os valores precisam ser armazenados como valores numéricos, e não como texto formatado.

Exemplo atual:

```text
$4,06
```

Representação desejada no banco:

```text
4.06
```

A moeda e a formatação devem ser responsabilidades da camada de apresentação.

---

### 8.4 Dados derivados

O campo:

```text
Dia de Semana
```

pode ser derivado de:

```text
Data Compra
```

Portanto, futuramente deverá ser avaliado se esse atributo precisa ser armazenado na camada de origem ou se deve ser calculado em uma dimensão de calendário.

---

### 8.5 Ausência de fonte automatizada

A entrada de dados depende atualmente de:

```text
Cupom
  ↓
Extração
  ↓
Revisão
  ↓
Cópia para Excel
```

Esse processo possui intervenção manual e pode gerar:

* erros de digitação;
* inconsistência de formatos;
* duplicidade;
* perda de informações;
* dificuldade de rastreabilidade.

---

## 9. Dados históricos

O projeto possui histórico de compras armazenado em uma planilha acumulada.

Algumas compras possuem as imagens originais dos cupons, porém não existe atualmente uma imagem disponível para todas as compras históricas.

Por esse motivo, a futura arquitetura deverá ser capaz de trabalhar com:

1. dados históricos já estruturados;
2. novos dados provenientes de cupons;
3. registros cuja origem original não está mais disponível.

---

## 10. Principais limitações da arquitetura atual

### Armazenamento

* Dependência do Excel;
* ausência de banco de dados;
* ausência de controle estruturado de schema.

### Ingestão

* Processo manual;
* ausência de pipeline automatizado;
* ausência de processamento sistemático dos cupons.

### Qualidade

* Ausência de testes automatizados;
* ausência de regras formais de Data Quality;
* inconsistências de nomes de produtos;
* possibilidade de duplicidades.

### Rastreabilidade

Atualmente não existe uma estrutura completa para responder:

```text
De qual arquivo veio esse registro?
Quando ele foi ingerido?
Quem o alterou?
Ele foi corrigido?
Qual foi a transformação aplicada?
```

### Orquestração

Não existe atualmente uma ferramenta responsável por coordenar o pipeline.

### Observabilidade

Não existem mecanismos estruturados de:

* logging;
* monitoramento;
* alertas;
* métricas de pipeline.

---

## 11. Arquitetura futura — visão inicial

A arquitetura futura será construída de forma incremental.

Uma primeira visão conceitual é:

```text
                    FONTES
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
      Excel/CSV              Cupom Fiscal
          │                       │
          │                      OCR
          │                       │
          └───────────┬───────────┘
                      ▼
                  INGESTÃO
                   Python
                      │
                      ▼
                    RAW
                      │
                      ▼
                   BRONZE
                      │
                      ▼
                Data Quality
                      │
                      ▼
                   SILVER
                      │
                      ▼
                    dbt
                      │
                      ▼
                    GOLD
                      │
                      ▼
              PostgreSQL / DW
                      │
                      ▼
                  Power BI
```

Componentes adicionais serão incorporados conforme surgirem necessidades reais:

* Airflow;
* Docker;
* AWS S3;
* IAM;
* Athena;
* CI/CD;
* PySpark;
* observabilidade.

---

## 12. Objetivos da evolução

A evolução do projeto deverá permitir:

* automatizar a ingestão;
* reduzir dependência de planilhas;
* armazenar dados de forma estruturada;
* preservar dados brutos;
* validar a qualidade dos dados;
* padronizar produtos;
* identificar compras individualmente quando possível;
* permitir reprocessamento;
* criar histórico das transformações;
* implementar testes;
* orquestrar pipelines;
* monitorar execuções;
* disponibilizar dados confiáveis para Analytics.

---

## 13. Princípios do projeto

Durante a evolução da plataforma serão adotados os seguintes princípios:

### Não alterar o dado bruto

A informação original deverá ser preservada sempre que possível.

### Não inventar informação

Quando não for possível determinar uma informação, ela deverá permanecer desconhecida ou nula.

### Automatizar progressivamente

A complexidade será adicionada conforme surgir necessidade real.

### Separar responsabilidades

Ingestão, transformação, qualidade, armazenamento e consumo devem possuir responsabilidades claras.

### Documentar decisões

Decisões arquiteturais relevantes deverão ser registradas no histórico arquitetural.

### Testar antes de confiar

Os dados e pipelines deverão possuir mecanismos de validação.

---

## 14. Estado atual

**Fase:** Engenharia reversa

**Versão:** V1 — Power BI

**Status:**

* [x] Fonte identificada
* [x] Granularidade identificada
* [x] Fluxo atual documentado
* [x] Principais problemas identificados
* [x] Limitações arquiteturais identificadas
* [ ] Modelo conceitual
* [ ] Modelo lógico
* [ ] Nova arquitetura
* [ ] Pipeline Python
* [ ] Banco de dados
* [ ] Data Quality
* [ ] dbt
* [ ] Airflow
* [ ] Cloud
* [ ] CI/CD
* [ ] Observabilidade

---

## 15. Próximos passos

1. Definir o modelo conceitual dos dados;
2. Definir entidades e relacionamentos;
3. Definir a granularidade das tabelas;
4. Definir chaves e identificadores;
5. Definir regras iniciais de Data Quality;
6. Projetar a arquitetura V2;
7. Implementar a primeira pipeline local;
8. Substituir progressivamente as transformações do Power Query por processos de Engenharia de Dados.
