def divide_lines(words, max_columns):
    lines = []
    current_line = ''
    words_left = words[:]
    while len(words_left):
        current_line = ''
        low = len(words) - len(words_left)
        while len(words_left):
            word = words_left[0]
            new_line = (current_line + ' ' + word).strip()
            if len(new_line) >= max_columns:
                break
            words_left = words_left[1:]
            current_line = new_line
        high = len(words) - len(words_left)
        lines.append((low, high))
    return lines
