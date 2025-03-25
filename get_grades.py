#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import PyPDF2
import pytesseract
from pdf2image import convert_from_path
import json
import os
from PIL import Image, ImageDraw
import uuid


def process_region(img, coords, is_numeric=False, custom_config=None, debug=False, debug_path=None, region_name=""):
    """Função independente para processar regiões de imagem"""
    try:
        region_img = img.crop(coords)

        if debug and debug_path:
            region_img.save(os.path.join(debug_path, f"region_{region_name}.png"))

        region_img = region_img.convert('L')  # Converter para escala de cinza
        threshold = 150
        region_img = region_img.point(lambda p: p > threshold and 255)

        if debug and debug_path:
            region_img.save(os.path.join(debug_path, f"processed_{region_name}.png"))

        text = pytesseract.image_to_string(region_img, config=custom_config)
        cleaned = ' '.join(text.strip().split())

        if is_numeric:
            numbers = re.findall(r'\d+[\.,]?\d*', cleaned)
            if numbers:
                return numbers[0].replace(',', '.')
            return 'N/A'

        return cleaned
    except Exception as e:
        print(f"Erro ao processar região: {e}")
        return 'N/A'


def extract_grades(img, width, height, custom_config, coordinates_json, debug=False, debug_path=None):
    """Extrai as notas das disciplinas usando coordenadas do JSON"""
    try:
        notas_coords = coordinates_json.get("notas_por_disciplina", {})
        grades = {}

        for disciplina, notas in notas_coords.items():
            if notas and len(notas) > 0:
                coord_data = notas[0]  # Pega o primeiro item (ignorando o campo "nota")

                # Cálculo modificado para corresponder ao script de captura
                x_center = coord_data["x"] * width
                y_center = coord_data["y"] * height
                half_width = (coord_data["largura"] * width) / 2
                half_height = (coord_data["altura"] * height) / 2

                # Calcula coordenadas absolutas
                x0 = int(x_center - half_width)
                y0 = int(y_center - half_height)
                x1 = int(x_center + half_width)
                y1 = int(y_center + half_height)

                coords = (x0, y0, x1, y1)
                region_id = f"nota_{disciplina.strip().lower().replace(' ', '_')}"

                grade = process_region(
                    img,
                    coords,
                    is_numeric=True,
                    custom_config=custom_config,
                    debug=debug,
                    debug_path=debug_path,
                    region_name=region_id
                )
                grades[disciplina.strip()] = grade

                if debug and debug_path:
                    debug_img = img.copy()
                    draw = ImageDraw.Draw(debug_img)
                    draw.rectangle(coords, outline="red", width=3)
                    debug_img.save(os.path.join(debug_path, f"marked_{region_id}.png"))

        return grades
    except Exception as e:
        print(f"Erro ao extrair notas: {e}")
        return {}


def extract_student_data(img, coordinates_json=None, debug=False, debug_path=None):
    """Extrai dados do aluno de uma única imagem de página"""
    try:
        width, height = img.size
        custom_config = r'--oem 3 --psm 6 -l por+eng'

        # Coordenadas das regiões de interesse (mantidas como no original)
        header_coords = (int(width * 0.50), 0, width, int(height * 0.10))
        student_data_coords = (0, int(height * 0.11), width, int(height * 0.19))

        header_text = process_region(
            img,
            header_coords,
            custom_config=custom_config,
            debug=debug,
            debug_path=debug_path,
            region_name="header"
        )

        student_text = process_region(
            img,
            student_data_coords,
            custom_config=custom_config,
            debug=debug,
            debug_path=debug_path,
            region_name="student_data"
        )

        combined_text = f"{header_text} {student_text}"

        patterns = {
            'Ano Letivo': r'(?:ANO|ANO\s+LETIVO)\s+(\d{4})',
            'Aluno(a)': r'ALUNO\(A\):\s*([A-ZÀ-ÜÇ\s]+?)\s*(?:NASCIMENTO|$)',
            'Matrícula': r'MATR[ÍI]CULA:\s*(\d+)',
        }

        data = {}
        for field, pattern in patterns.items():
            match = re.search(pattern, combined_text, re.IGNORECASE)
            data[field] = match.group(1).strip() if match else 'N/A'

        # Extrai notas usando as coordenadas do JSON
        if coordinates_json:
            data['Disciplinas'] = extract_grades(
                img,
                width,
                height,
                custom_config,
                coordinates_json,
                debug=debug,
                debug_path=debug_path
            )
        else:
            data['Disciplinas'] = {}

        return data

    except Exception as e:
        print(f"Erro ao extrair dados da página: {e}")
        return {"error": str(e)}


def get_pdf_page_count(pdf_path):
    """Método mais confiável para contar páginas do PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            return len(reader.pages)
    except Exception as e:
        print(f"Erro ao contar páginas do PDF: {e}")
        return 0


def process_pdf(pdf_path, output_file, coordinates_json=None, batch_size=3, debug=False, debug_path=None):
    """Processa todas as páginas do PDF corretamente"""
    total_pages = get_pdf_page_count(pdf_path)
    if total_pages == 0:
        print("Não foi possível determinar o número de páginas do PDF")
        return False

    print(f"PDF contém {total_pages} páginas confirmadas")

    all_data = []
    processed_pages = 0

    while processed_pages < total_pages:
        start_page = processed_pages + 1
        end_page = min(processed_pages + batch_size, total_pages)

        print(f"\nConvertendo páginas {start_page} a {end_page}...")
        try:
            images = convert_from_path(
                pdf_path,
                first_page=start_page,
                last_page=end_page,
                dpi=400,
                thread_count=2,
                poppler_path='/usr/bin',
                fmt='jpeg'
            )

            print(f"Convertidas {len(images)} imagens para processamento")

            for i, img in enumerate(images):
                current_page = processed_pages + i + 1
                print(f"\nProcessando página {current_page}/{total_pages}...")

                try:
                    # Cria subpasta para debug da página atual se necessário
                    page_debug_path = None
                    if debug and debug_path:
                        page_debug_path = os.path.join(debug_path, f"page_{current_page}")
                        os.makedirs(page_debug_path, exist_ok=True)

                    # Salva imagem completa da página se debug ativado
                    if debug and page_debug_path:
                        img.save(os.path.join(page_debug_path, "full_page.png"))

                    student_data = extract_student_data(
                        img,
                        coordinates_json,
                        debug=debug,
                        debug_path=page_debug_path
                    )

                    if student_data:
                        all_data.append(student_data)
                        print(f"✅ Dados extraídos: {student_data.get('Aluno(a)', 'N/A')}")
                    else:
                        all_data.append({"error": f"Falha na página {current_page}"})
                        print("❌ Falha ao extrair dados")
                except Exception as page_error:
                    print(f"Erro na página {current_page}: {str(page_error)}")
                    all_data.append({"error": f"Erro na página {current_page}: {str(page_error)}"})

                # Salvar progresso após cada página
                with open(output_file, 'w') as f:
                    json.dump(all_data, f, indent=2, ensure_ascii=False)

            processed_pages += len(images)

        except Exception as batch_error:
            print(f"\nErro no lote de páginas {start_page}-{end_page}: {batch_error}")
            print("Salvando progresso atual...")
            with open(output_file, 'w') as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            return False

    print("\nProcessamento concluído com sucesso!")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Processa boletins escolares em PDF')
    parser.add_argument('pdf_path', help='Caminho para o arquivo PDF')
    parser.add_argument('-o', '--output', required=True, help='Arquivo de saída JSON')
    parser.add_argument('-b', '--batch', type=int, default=3, help='Tamanho do lote de páginas (padrão: 3)')
    parser.add_argument('-c', '--coordinates', required=True, help='Arquivo JSON com as coordenadas das notas')
    parser.add_argument('-d', '--debug', action='store_true', help='Ativa modo debug (salva imagens processadas)')
    parser.add_argument('--debug-path', default="debug_output",
                        help='Pasta para salvar arquivos de debug (padrão: debug_output)')
    args = parser.parse_args()

    print(f"\nIniciando processamento de {args.pdf_path}")

    # Verificação adicional do arquivo PDF
    if not os.path.exists(args.pdf_path):
        print("Erro: Arquivo PDF não encontrado!")
        return

    # Carrega o arquivo de coordenadas se fornecido
    coordinates_json = None
    if args.coordinates:
        try:
            with open(args.coordinates, 'r') as f:
                coordinates_json = json.load(f)
            print("Coordenadas carregadas com sucesso do arquivo JSON")
        except Exception as e:
            print(f"Erro ao carregar arquivo de coordenadas: {e}")
            return

    # Prepara pasta de debug se necessário
    if args.debug:
        os.makedirs(args.debug_path, exist_ok=True)
        print(f"Modo debug ativado. Arquivos serão salvos em: {args.debug_path}")

    file_size = os.path.getsize(args.pdf_path) / (1024 * 1024)  # Tamanho em MB
    print(f"Tamanho do arquivo: {file_size:.2f} MB")

    success = process_pdf(
        args.pdf_path,
        args.output,
        coordinates_json,
        args.batch,
        debug=args.debug,
        debug_path=args.debug_path
    )

    if success:
        print(f"\nDados salvos em {args.output}")
        with open(args.output, 'r') as f:
            data = json.load(f)
        print(f"Total de boletins processados: {len(data)}")

        # Verificação adicional
        if len(data) != get_pdf_page_count(args.pdf_path):
            print("\n⚠️ Aviso: O número de boletins processados não corresponde ao número de páginas!")
            print("Possíveis causas:")
            print("- Algumas páginas podem ter falhado no processamento")
            print("- O PDF pode conter páginas não relacionadas a boletins")
            print("- Verifique o arquivo de saída para detalhes")
    else:
        print("\nProcessamento encontrou erros, verifique o arquivo de saída para dados parciais")


if __name__ == "__main__":
    main()
