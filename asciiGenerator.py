from PIL import Image

# Общая палитра символов (от темного к светлому)
ASCII_PALETTE = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

def generate_ascii_art(image_path, output_width=200):
    """Генерирует ASCII-арт в цветном или ч/б режиме"""
    img = Image.open(image_path)
    
    # Рассчет высоты с учетом пропорций символов
    aspect_ratio = img.height / img.width
    output_height = int(output_width * aspect_ratio * 0.5)
    
    # Масштабирование
    img = img.resize((output_width, output_height), Image.LANCZOS)
    
    pixels = img.load()
    ascii_lines = []
    
    for y in range(output_height):
        line = []
        for x in range(output_width):
            # Обработка пикселя в зависимости от режима
            r, g, b = pixels[x, y]
            brightness = 0.299 * r + 0.587 * g + 0.114 * b
            char = ASCII_PALETTE[int(brightness / 255 * (len(ASCII_PALETTE) - 1))]
            line.append(f"\033[38;2;{r};{g};{b}m{char}")

        # Для цветного режима добавляем сброс цвета в конце строки
        ascii_lines.append("".join(line) + ("\033[0m"))
    
    return "\n".join(ascii_lines)

def generate(path):    
# Генерация цветного ASCII
    color_ascii = generate_ascii_art(path)
    with open("ascii_art.txt", "w", encoding="utf-8") as f:
        f.write(color_ascii)
        print(color_ascii)
        