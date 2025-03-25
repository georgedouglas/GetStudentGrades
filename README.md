# Aplicação de Extração de Notas Escolares

## Visão Geral

Esta aplicação consiste em dois scripts que trabalham juntos para:

1. **Detectar as posições** das disciplinas e notas em boletins escolares (`get_grade_coords.py`)
2. **Extrair os dados** dos alunos e suas notas (`get_grades.py`)

## Como Funciona

1. Primeiro, você usa `get_grade_coords.py` para analisar um boletim e criar um arquivo de coordenadas (JSON)
2. Depois, usa `get_grades.py` com esse arquivo de coordenadas para extrair automaticamente todas as notas

## Arquivo de Coordenadas (Obrigatório)

O arquivo JSON de coordenadas é **essencial** para o funcionamento correto do sistema. Ele contém:

- Posições exatas onde estão as disciplinas e notas no boletim
- Tamanhos das áreas onde os dados aparecem
- Relação entre cada disciplina e sua respectiva nota

## Instruções Básicas

### 1. Criar o arquivo de coordenadas
```bash
python get_grade_coords.py boletim.pdf -o coordenadas.json
```

### 2. Extrair os dados
```bash
python get_grades.py boletim.pdf -o notas.json -c coordenadas.json
```

## Benefícios

- Automatiza a extração de dados de boletins escolares
- Elimina a necessidade de digitação manual
- Funciona mesmo com layouts complexos de boletins
- Pode processar vários boletins de uma vez

## Requisitos

- Python 3 instalado
- Bibliotecas: pytesseract, pdf2image, Pillow, opencv-python, numpy, PyPDF2
- Tesseract OCR instalado no sistema

# Documentação dos Scripts

## `get_grade_coords.py`

Script para extrair coordenadas de disciplinas e notas de boletins escolares em PDF e salvar em formato JSON.

### Funções Principais

#### `safe_crop(image, x0, y0, x1, y1)`
- **Descrição**: Garante que o recorte esteja dentro dos limites da imagem
- **Parâmetros**:
  - `image`: Imagem a ser recortada
  - `x0, y0`: Coordenadas do canto superior esquerdo
  - `x1, y1`: Coordenadas do canto inferior direito
- **Retorno**: Imagem recortada ou None se inválido

#### `save_coordinates_to_json(matched_data, output_filename, img_width, img_height)`
- **Descrição**: Salva as coordenadas em arquivo JSON com disciplinas e notas
- **Parâmetros**:
  - `matched_data`: Dados combinados de disciplinas e notas
  - `output_filename`: Nome do arquivo de saída
  - `img_width, img_height`: Dimensões da imagem

#### `detect_individual_notes(pdf_path, page_num=0, padding=10)`
- **Descrição**: Detecta notas individuais na coluna de notas
- **Parâmetros**:
  - `pdf_path`: Caminho do PDF
  - `page_num`: Número da página (0-based)
  - `padding`: Espaçamento ao redor das notas
- **Retorno**: Tupla (imagem, lista de notas detectadas)

#### `extract_subjects(img, width, height)`
- **Descrição**: Extrai nomes de disciplinas ignorando regiões específicas
- **Parâmetros**:
  - `img`: Imagem da página
  - `width, height`: Dimensões da imagem
- **Retorno**: Tupla (lista de disciplinas, lista de caixas delimitadoras)

#### `match_notes_with_subjects(notes, subjects, subject_boxes)`
- **Descrição**: Associa notas às disciplinas correspondentes
- **Parâmetros**:
  - `notes`: Lista de notas detectadas
  - `subjects`: Lista de disciplinas
  - `subject_boxes`: Caixas delimitadoras das disciplinas
- **Retorno**: Lista de dicionários com associações

#### `draw_matches(img, matched_data)`
- **Descrição**: Desenha marcações conectando disciplinas e notas
- **Parâmetros**:
  - `img`: Imagem original
  - `matched_data`: Dados combinados
- **Retorno**: Imagem com marcações

### Uso via Linha de Comando
```bash
python get_grade_coords.py caminho_do_pdf.pdf -o output.json [-p pagina] [-pd padding]
```

### Argumentos
- `pdf_path`: Caminho para o arquivo PDF
- `-o/--output`: Nome do arquivo JSON de saída (obrigatório)
- `-p/--page`: Número da página a processar (padrão: 0)
- `-pd/--padding`: Padding para detecção (padrão: 10)

---

## `get_grades.py`

Script para extrair dados de alunos e notas de boletins escolares usando OCR.

### Funções Principais

#### `process_region(img, coords, is_numeric=False, custom_config=None, debug=False, debug_path=None, region_name="")`
- **Descrição**: Processa uma região de imagem com OCR
- **Parâmetros**:
  - `img`: Imagem fonte
  - `coords`: Coordenadas da região
  - `is_numeric`: Se deve extrair apenas números
  - `custom_config`: Configuração do Tesseract
  - `debug`: Ativa modo debug
  - `debug_path`: Pasta para salvar imagens debug
  - `region_name`: Nome da região para debug
- **Retorno**: Texto extraído

#### `extract_grades(img, width, height, custom_config, coordinates_json, debug=False, debug_path=None)`
- **Descrição**: Extrai notas usando coordenadas do JSON
- **Parâmetros**:
  - `img`: Imagem da página
  - `width, height`: Dimensões
  - `custom_config`: Configuração OCR
  - `coordinates_json`: Dados de coordenadas
  - `debug`: Modo debug
  - `debug_path`: Pasta debug
- **Retorno**: Dicionário de disciplinas e notas

#### `extract_student_data(img, coordinates_json=None, debug=False, debug_path=None)`
- **Descrição**: Extrai dados do aluno (nome, matrícula, etc.)
- **Parâmetros**:
  - `img`: Imagem da página
  - `coordinates_json`: Coordenadas das notas
  - `debug`: Modo debug
  - `debug_path`: Pasta debug
- **Retorno**: Dicionário com dados do aluno

#### `get_pdf_page_count(pdf_path)`
- **Descrição**: Conta páginas do PDF de forma confiável
- **Parâmetros**:
  - `pdf_path`: Caminho do PDF
- **Retorno**: Número de páginas

#### `process_pdf(pdf_path, output_file, coordinates_json=None, batch_size=3, debug=False, debug_path=None)`
- **Descrição**: Processa todas as páginas do PDF
- **Parâmetros**:
  - `pdf_path`: Caminho do PDF
  - `output_file`: Arquivo JSON de saída
  - `coordinates_json`: Dados de coordenadas
  - `batch_size`: Tamanho do lote de páginas
  - `debug`: Modo debug
  - `debug_path`: Pasta debug
- **Retorno**: Booleano indicando sucesso

### Uso via Linha de Comando
```bash
python get_grades.py caminho_do_pdf.pdf -o output.json [-b batch_size] [-c coordinates.json] [-d] [--debug-path pasta]
```

### Argumentos
- `pdf_path`: Caminho para o arquivo PDF
- `-o/--output`: Arquivo de saída JSON (obrigatório)
- `-b/--batch`: Tamanho do lote de páginas (padrão: 3)
- `-c/--coordinates`: Arquivo JSON com coordenadas
- `-d/--debug`: Ativa modo debug
- `--debug-path`: Pasta para arquivos debug (padrão: "debug_output")

### Requisitos
- Python 3.11
- Bibliotecas: `pytesseract`, `pdf2image`, `Pillow`, `opencv-python`, `numpy`, `PyPDF2`

### Observações
1. Para melhor precisão no OCR, ajuste as coordenadas conforme necessário
2. O modo debug ajuda a verificar se as regiões estão sendo detectadas corretamente
3. O arquivo de coordenadas é opcional, mas melhora a precisão na extração de notas
