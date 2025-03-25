import json
import argparse
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import cv2
import numpy as np


def safe_crop(image, x0, y0, x1, y1):
    """Garante que o recorte esteja dentro dos limites da imagem"""
    h, w = image.shape[:2] if len(image.shape) == 3 else image.shape
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)

    if x0 >= x1 or y0 >= y1:
        return None

    return image[y0:y1, x0:x1]


def save_coordinates_to_json(matched_data, output_filename, img_width, img_height):
    """Salva as coordenadas em um arquivo JSON com disciplinas e suas notas correspondentes, incluindo tamanhos"""
    try:
        result = {
            'disciplinas': {},
            'notas_por_disciplina': {},
            'imagem_dimensoes': {
                'largura': img_width,
                'altura': img_height
            }
        }

        disciplina_x0 = int(img_width * 0.02)  # Coordenada x fixa para todas as disciplinas

        for item in matched_data:
            # Coordenadas e tamanho da disciplina
            subject_coords = item['subject_coords']
            y_center = (subject_coords[1] + subject_coords[3]) / 2
            y_relative = y_center / img_height
            width_subject = subject_coords[2] - subject_coords[0]
            height_subject = subject_coords[3] - subject_coords[1]

            # Adiciona ao dicionário de disciplinas
            result['disciplinas'][item['subject']] = {
                'x': disciplina_x0,
                'y': y_relative,
                'largura': width_subject / img_width,
                'altura': height_subject / img_height
            }

            # Coordenadas e tamanho da nota
            note_coords = item['note_coords']
            x_center = (note_coords[0] + note_coords[2]) / 2
            y_center = (note_coords[1] + note_coords[3]) / 2
            x_relative = x_center / img_width
            y_relative = y_center / img_height
            width_note = note_coords[2] - note_coords[0]
            height_note = note_coords[3] - note_coords[1]

            # Adiciona ao dicionário de notas por disciplina
            if item['subject'] not in result['notas_por_disciplina']:
                result['notas_por_disciplina'][item['subject']] = []

            result['notas_por_disciplina'][item['subject']].append({
                'nota': item['note'],
                'x': x_relative,
                'y': y_relative,
                'largura': width_note / img_width,
                'altura': height_note / img_height
            })

        # Salva em arquivo JSON
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        print(f"Coordenadas salvas com sucesso em {output_filename}")
        return True
    except Exception as e:
        print(f"Erro ao salvar coordenadas: {str(e)}")
        return False


def detect_individual_notes(pdf_path, page_num=0, padding=10):
    """Detecta e marca cada nota individualmente na coluna de notas"""
    try:
        # Converte o PDF para imagem
        images = convert_from_path(pdf_path, first_page=page_num + 1, last_page=page_num + 1, dpi=500)
        if not images:
            print("Nenhuma imagem encontrada no PDF.")
            return None, None

        img = images[0]
        width, height = img.size

        # Verifica se a imagem foi carregada corretamente
        if width == 0 or height == 0:
            print("Dimensões inválidas da imagem convertida.")
            return None, None

        # Converte para OpenCV format (BGR)
        open_cv_image = np.array(img)
        if open_cv_image.size == 0:
            print("Falha ao converter imagem para formato OpenCV.")
            return None, None

        open_cv_image = open_cv_image[:, :, ::-1].copy()  # Convert RGB to BGR

        # Define a região aproximada da coluna de notas (ajuste conforme necessário)
        notes_region_x0 = int(width * 0.5930)
        notes_region_x1 = int(width * 0.6315)
        notes_region_y0 = int(height * 0.26)
        notes_region_y1 = int(height * 0.685)

        # Recorta a região de interesse com verificação de limites
        roi = safe_crop(open_cv_image, notes_region_x0, notes_region_y0, notes_region_x1, notes_region_y1)
        if roi is None:
            print("Região de interesse (ROI) está vazia ou inválida. Ajuste as coordenadas da região de notas.")
            return None, None

        # Pré-processamento da imagem para melhorar o OCR
        try:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        except Exception as e:
            print(f"Erro no pré-processamento da imagem: {str(e)}")
            return None, None

        # Configuração do Tesseract para detectar apenas dígitos
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,'

        # Executa o OCR
        try:
            data = pytesseract.image_to_data(thresh, config=custom_config, output_type=pytesseract.Output.DICT)
        except Exception as e:
            print(f"Erro ao executar OCR: {str(e)}")
            return None, None

        # Processa os resultados para encontrar las notas individuales
        individual_notes = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if text and (text.isdigit() or '.' in text or ',' in text):
                x = data['left'][i] + notes_region_x0
                y = data['top'][i] + notes_region_y0
                w = data['width'][i]
                h = data['height'][i]

                # Aplica padding às coordenadas (garantindo que não ultrapasse os limites da imagem)
                x0 = max(0, x - padding)
                y0 = max(0, y - padding)
                x1 = min(width, x + w + padding)
                y1 = min(height, y + h + padding)

                # Verifica se a caixa delimitadora é válida
                if x0 < x1 and y0 < y1:
                    box_coords = (x0, y0, x1, y1)
                    individual_notes.append({
                        'text': text,
                        'coords': box_coords,
                        'original_coords': (x, y, x + w, y + h)
                    })

        # Se não encontrou notas, retorna None
        if not individual_notes:
            print("Nenhuma nota foi detectada na região especificada.")
            return None, None

        return img, individual_notes

    except Exception as e:
        print(f"Erro inesperado em detect_individual_notes: {str(e)}")
        return None, None


def extract_subjects(img, width, height):
    """Extrai os nomes das disciplinas ignorando regiões específicas"""
    try:
        # Converte a imagem para OpenCV (BGR)
        open_cv_image = np.array(img)
        if open_cv_image.size == 0:
            print("Imagem vazia na extração de disciplinas.")
            return [], []

        open_cv_image = open_cv_image[:, :, ::-1].copy()  # Convert RGB to BGR

        # Define a região principal das disciplinas
        main_region = {
            'x0': int(width * 0.02),
            'y0': int(height * 0.245),
            'x1': int(width * 0.3575),
            'y1': int(height * 0.685)
        }

        # Verifica se a região principal é válida
        if (main_region['x0'] >= main_region['x1'] or
                main_region['y0'] >= main_region['y1'] or
                main_region['x1'] > width or
                main_region['y1'] > height):
            print("Região principal de disciplinas inválida.")
            return [], []

        # Regiões a serem ignoradas (coordenadas absolutas)
        ignore_regions = [
            {
                'x0': int(width * 0.02),
                'y0': int(height * 0.245),
                'x1': int(width * 0.3575),
                'y1': int(height * 0.26)
            },
            {
                'x0': int(width * 0.02),
                'y0': int(height * 0.326),
                'x1': int(width * 0.3575),
                'y1': int(height * 0.34)
            },
            {
                'x0': int(width * 0.02),
                'y0': int(height * 0.426),
                'x1': int(width * 0.3575),
                'y1': int(height * 0.441)
            },
            {
                'x0': int(width * 0.02),
                'y0': int(height * 0.527),
                'x1': int(width * 0.3575),
                'y1': int(height * 0.5415)
            },
            {
                'x0': int(width * 0.02),
                'y0': int(height * 0.5635),
                'x1': int(width * 0.3575),
                'y1': int(height * 0.5765)
            }
        ]

        # Pré-processamento global
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        # Divide a região principal em faixas verticais válidas
        valid_regions = []
        current_y = main_region['y0']

        # Ordena as regiões a ignorar por coordenada y
        ignore_regions_sorted = sorted(ignore_regions, key=lambda r: r['y0'])

        for ignore in ignore_regions_sorted:
            if ignore['y0'] > current_y:
                # Adiciona a região válida entre a atual e a região a ignorar
                valid_regions.append({
                    'x0': main_region['x0'],
                    'y0': current_y,
                    'x1': main_region['x1'],
                    'y1': ignore['y0']
                })
            current_y = max(current_y, ignore['y1'])

        # Adiciona a última região válida
        if current_y < main_region['y1']:
            valid_regions.append({
                'x0': main_region['x0'],
                'y0': current_y,
                'x1': main_region['x1'],
                'y1': main_region['y1']
            })

        # Processa cada região válida
        subjects = []
        subject_boxes = []
        for region in valid_regions:
            # Recorta a região válida com verificação de limites
            roi = safe_crop(thresh, region['x0'], region['y0'], region['x1'], region['y1'])
            if roi is None:
                continue

            # Detecção de linhas horizontais dentro da região válida
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
            detect_horizontal = cv2.morphologyEx(roi, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)

            # Encontra contornos das linhas
            cnts = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]

            # Ordena os contornos de cima para baixo
            cnts = sorted(cnts, key=lambda c: cv2.boundingRect(c)[1])

            # Coordenadas y das linhas (relativas à região)
            y_coords = [0] + [cv2.boundingRect(c)[1] for c in cnts] + [roi.shape[0]]

            # Processa cada área entre as linhas
            for i in range(len(y_coords) - 1):
                y_start = y_coords[i]
                y_end = y_coords[i + 1]

                # Recorta a área da possível disciplina
                subject_area = safe_crop(roi, 0, y_start, roi.shape[1], y_end)
                if subject_area is None:
                    continue

                # Configuração do Tesseract
                custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'

                # Executa o OCR
                text = pytesseract.image_to_string(subject_area, config=custom_config, lang='por')
                text = ' '.join(text.split()).strip()

                # Filtra resultados
                if (len(text) > 3 and
                        any(c.isalpha() for c in text) and
                        not any(text.startswith(prefix) for prefix in [' ', '.', ',', ';', '-'])):

                    # Pós-processamento do texto
                    clean_text = text.split('\n')[0].strip()
                    clean_text = ''.join(
                        c for c in clean_text if c.isalnum() or c in ' -áéíóúâêîôûãõàèìòùçÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ')

                    if len(clean_text.split()) >= 1:
                        # Calcula as coordenadas da caixa da disciplina
                        box_x0 = region['x0']
                        box_y0 = region['y0'] + y_start
                        box_x1 = region['x1']
                        box_y1 = region['y0'] + y_end

                        subjects.append(clean_text)
                        subject_boxes.append({
                            'text': clean_text,
                            'coords': (box_x0, box_y0, box_x1, box_y1)
                        })

        return subjects, subject_boxes

    except Exception as e:
        print(f"Erro inesperado em extract_subjects: {str(e)}")
        return [], []


def match_notes_with_subjects(notes, subjects, subject_boxes):
    """Associa cada nota à disciplina correspondente pela ordem de aparição"""
    try:
        matched = []
        min_length = min(len(notes), len(subjects))

        for i in range(min_length):
            matched.append({
                'subject': subjects[i],
                'subject_coords': subject_boxes[i]['coords'],
                'note': notes[i]['text'],
                'note_coords': notes[i]['coords']
            })

        return matched
    except Exception as e:
        print(f"Erro inesperado em match_notes_with_subjects: {str(e)}")
        return []


def draw_matches(img, matched_data):
    """Desenha as marcações e linhas conectando notas e disciplinas"""
    try:
        img_with_boxes = img.copy()
        draw = ImageDraw.Draw(img_with_boxes)

        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()

        # Cores diferentes para cada par nota-disciplina
        colors = ["red", "blue", "green", "purple", "orange", "brown", "pink", "gray"]

        for i, item in enumerate(matched_data):
            color = colors[i % len(colors)]

            # Desenha retângulo ao redor da disciplina
            subject_coords = item['subject_coords']
            draw.rectangle(subject_coords, outline=color, width=2)

            # Desenha o texto da disciplina acima do retângulo
            text_position = (subject_coords[0], subject_coords[1] - 25)
            draw.text(text_position, item['subject'], fill=color, font=font)

            # Desenha retângulo ao redor da nota
            note_coords = item['note_coords']
            draw.rectangle(note_coords, outline=color, width=2)

            # Desenha o texto da nota acima do retângulo
            text_position = (note_coords[0], note_coords[1] - 25)
            draw.text(text_position, item['note'], fill=color, font=font)

            # Desenha linha conectando a disciplina à nota
            start_x = subject_coords[2]  # Lado direito da caixa da disciplina
            start_y = (subject_coords[1] + subject_coords[3]) // 2  # Centro vertical
            end_x = note_coords[0]  # Lado esquerdo da caixa da nota
            end_y = (note_coords[1] + note_coords[3]) // 2  # Centro vertical

            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=2)

        return img_with_boxes
    except Exception as e:
        print(f"Erro inesperado em draw_matches: {str(e)}")
        return img


def main():
    # Configuração dos argumentos de linha de comando
    parser = argparse.ArgumentParser(description='Extrai notas e disciplinas de boletins escolares')
    parser.add_argument('pdf_path', help='Caminho para o arquivo PDF do boletim')
    parser.add_argument('-o', '--output', required=True, help='Nome do arquivo JSON para salvar as coordenadas')
    parser.add_argument('-p', '--page', type=int, default=0, help='Número da página a ser processada (0-based)')
    parser.add_argument('-pd', '--padding', type=int, default=10, help='Padding para as caixas de detecção')

    args = parser.parse_args()

    try:
        # Converte o PDF para imagem
        images = convert_from_path(args.pdf_path, first_page=args.page + 1, last_page=args.page + 1, dpi=500)
        if not images:
            print("Nenhuma imagem encontrada no PDF.")
            return

        img = images[0]
        width, height = img.size

        # Extrai os nomes das disciplinas e suas coordenadas
        subjects, subject_boxes = extract_subjects(img, width, height)
        if not subjects:
            print("Nenhuma disciplina foi detectada.")
            return

        # Detecta as notas individuais
        img, notes = detect_individual_notes(args.pdf_path, args.page, args.padding)
        if not notes:
            return

        # Associa notas com disciplinas
        matched_data = match_notes_with_subjects(notes, subjects, subject_boxes)

        # Desenha as marcações e linhas
        img_with_boxes = draw_matches(img, matched_data)

        # Mostra a imagem com as marcações
        img_with_boxes.show()

        # Salva as coordenadas em JSON
        if not save_coordinates_to_json(matched_data, args.output, width, height):
            return

        # Mostra resultados no console
        if matched_data:
            print("\nDisciplinas detectadas:")
            for i, subject in enumerate(subjects, 1):
                print(f"{i}. {subject}")

            print("\nNotas associadas às disciplinas:")
            for item in matched_data:
                print(f"Disciplina: {item['subject']} | Nota: {item['note']}")

    except Exception as e:
        print(f"Erro inesperado: {str(e)}")


if __name__ == "__main__":
    main()
