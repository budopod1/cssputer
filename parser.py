class CCASyntaxError(ValueError):
    pass


def parse(text, show_var_locations=True):
    code_lines = []
    data_lines = []
    number_lines = []
    table_lines = []

    section = code_lines
    for line in text.split("\n"):
        if line == "":
            section = None
        elif line.endswith(":"):
            section_map = {
                "DATA:": data_lines,
                "NUMBERS:": number_lines,
                "TABLES:": table_lines,
            }
            if line not in section_map:
                raise CCASyntaxError()
            section = section_map[line]
        else:
            if section is None:
                raise CCASyntaxError()
            section.append(line)

    variables = {}

    for data_line in data_lines:
        try:
            name, value = map(str.strip, data_line.split("="))
        except ValueError:
            raise CCASyntaxError()
        try:
            variables[name] = int(value, 16)
        except ValueError:
            raise CCASyntaxError()

    tables = {}

    for table_line in table_lines:
        before, sep, nums_txt = table_line.partition(":")
        if not sep:
            raise CCASyntaxError()
        count_txt, sep, name = before.partition(" ")
        if not sep:
            raise CCASyntaxError()
        try:
            count = int(count_txt, 16)
        except ValueError:
            if count_txt in variables:
                count = variables[count_txt]
            else:
                raise CCASyntaxError()
        nums = [0 for _ in range(count)]
        for i, num_txt in enumerate(nums_txt.split()):
            try:
                nums[i] = int(num_txt, 16)
            except ValueError:
                raise CCASyntaxError()
        tables[name] = nums

    numbers = set()

    for number_line in number_lines:
        parts = number_line.split()
        previous = []
        for part in parts:
            if part == "...":
                previous.append(part)
                continue
            try:
                num = int(part, 16)
                previous.append(num)
                numbers.add(num)
            except ValueError:
                raise CCASyntaxError()
            if len(previous) >= 2 and previous[-2] == "...":
                if len(previous) < 3:
                    raise CCASyntaxError()
                numbers.update(range(previous[-3], previous[-1]+1))

    for number in numbers:
        variables[str(number)] = number % 256

    result = [0, 0]
    # add code placeholder
    result.extend([0, 0] * len(code_lines))

    variable_locations = {"A": 0}

    # for name, value in variables.items():
    #     variable_locations[name] = len(result)
    #     result.append(value)

    while tables or variables:
        next_loc = len(result)
        added_table = False
        for name, values in tables.items():
            required_bits = (len(values)-1).bit_length()
            if next_loc >> required_bits << required_bits == next_loc:
                del tables[name]
                variable_locations[name] = next_loc
                result.extend(values)
                added_table = True
                break
        if added_table:
            continue
        if variables:
            name, value = variables.popitem()
            variable_locations[name] = next_loc
            result.append(value)
        else:
            result.append(0)

    if show_var_locations:
        print(variable_locations)

    i = 2
    for code_line in code_lines:
        if not code_line:
            raise CCASyntaxError()
        cmd, *operand_txts = code_line.split()
        command_map = {
            "EXIT": 0,
            "LOAD": 1,
            "STOR": 2,
            "ADD": 3,
            "SWAP": 4,
            "MULT": 5,
            "INV": 6,
            "GOTO": 7,
            "SKIP": 8,
            "LEAP": 9,
            "INDX": 10,
            "EQ": 11,
            'GTEQ': 12
        }
        if cmd not in command_map:
            raise CCASyntaxError()
        cmd_code = command_map[cmd]
        operand = 0
        if cmd not in ["EXIT", "INV"]:
            try:
                operand_txt, = operand_txts
            except IndexError:
                raise CCASyntaxError()
            if cmd in ["GOTO"]:
                try:
                    operand = int(operand_txt, 16) - 1
                except ValueError:
                    raise CCASyntaxError()
            else:
                if operand_txt not in variable_locations:
                    raise CCASyntaxError()
                operand = variable_locations[operand_txt]
        result[i] = cmd_code
        result[i+1] = operand
        i += 2

    return result
