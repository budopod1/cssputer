import parser
from blocks import Hardware, BitChain, OneHot, MemNumber, Array, Counter, Bool

"""
INSTRUCTION SET:
0x00 EXIT: halt execution
    A. halt execution
0x01 LOAD: loads the specified value into the accumulator
    A. load from storage to accumulator
0x02 STOR: transfers the accumulator's value to storage
    A. transfer from accumulator to storage
0x03 ADD: adds the specified value to the accumulator
    A. load from storage and compute addition, storing result to intermediate
    B. load from intermediate to accumulator
0x04 SWAP: swaps the specified value and the accumulator
    A. load from storage to intermediate
    B. store the accumulator to storage
    C. load from intermediate to accumulator
0x05 MULT: multiplies the accumulator by the specified value
    A. load from storage and compute multiplication, storing result to intermediate
    B. load from intermediate to accumulator
0x06 INV: inverts the accumulator's value
    A. store the accumulator to intermediate
    B. store intermediate inverted to the accumulator
0x07 GOTO: moves the instruction pointer to the specified address
    A. store the specified address into the instruction pointer
0x08 SKIP: skips the next instruction if the specified value is not equal to zero
    A. load the value from memory
    B. increment the instruction pointer if the value doesn't equal zero
0x09 LEAP: moves the instruction pointer to the specified value as an address
    A. store the specified value into the instruction pointer
0x0A INDX: set the op address offset to the specified value
    A. assign the index to the specified value
0x0B EQ: determines if the accumulator and specified value are equal, storing the result 0x00 or 0xFF,
into the accumulator
    A. store whether the accumulator equals the specified value in intermediate
    B. set the accumulator to the value stored in intermediate
0x0C GTEQ: determines if the accumulator's value is greater than or equal to the specified value
    A. store whether the accumulator is greater or equal to the specified value in intermediate
    B. set the accumulator to the value stored in intermediate

SPECIAL MEMORY POSITIONS:
0x00: the accumulator
0x01: reserved for future use
"""


def main():
    memory_size = 64
    bit_width = 8

    with open("triangle2.cca") as file:
        code = file.read()
    starting_memory = parser.parse(code)
    if len(starting_memory) >= memory_size:
        raise ValueError("Not enough memory for the given program")

    hardware = Hardware()

    phase = BitChain(hardware, 6)
    op_code = OneHot(hardware, 13)
    op_address = MemNumber(hardware, bit_width)
    index = MemNumber(hardware, bit_width)
    intermediate = MemNumber(hardware, bit_width)
    carries = hardware.alloc(2*bit_width*bit_width-3*bit_width+2)
    memory = Array(hardware, memory_size, bit_width, bit_width, starting_memory)
    instruction_pointer = Counter(hardware, bit_width)
    freezer_bit = hardware.bit()

    freezer_bit.set(False)
    accumulator = MemNumber.from_(hardware, memory[0])

    phase_0 = phase.exactly(0)
    instruction_pointer.count(phase_0)

    phase_1 = phase.exactly(1)
    op_code_idx = instruction_pointer << 1
    op_code.set_source(memory.get(op_code_idx, phase_1), phase_1)

    phase_2 = phase.exactly(2)
    op_code_address = op_code_idx | 1
    op_address.assign(memory.get(op_code_address, phase_2), phase_2)

    phase_3 = phase.exactly(3)
    phase_4 = phase.exactly(4)
    phase_5 = phase.exactly(5)

    ref_address = op_address | index

    load_op_codes = [1, 3, 4, 5, 8, 9, 11, 12]
    loaded = memory.get(ref_address, phase_3 & Bool.or_(*(op_code[code] for code in load_op_codes)))

    freezer_bit.if_(phase_3 & op_code[0])

    accumulator.assign(loaded, phase_4 & op_code[1])

    memory.set(ref_address, accumulator, phase_3 & op_code[2])

    intermediate.assign(accumulator.add(loaded, phase_3 & op_code[3], list(carries)), phase_3 & op_code[3])
    accumulator.assign(intermediate, phase_4 & op_code[3])

    intermediate.assign(loaded, phase_3 & op_code[4])
    memory.set(ref_address, accumulator, phase_4 & op_code[4])
    accumulator.assign(intermediate, phase_5 & op_code[4])

    intermediate.assign(accumulator.mult(loaded, phase_3 & op_code[5], list(carries)), phase_3 & op_code[5])
    accumulator.assign(intermediate, phase_4 & op_code[5])

    intermediate.assign(accumulator, phase_3 & op_code[6])
    accumulator.assign(~intermediate, phase_4 & op_code[6])

    instruction_pointer.assign(op_address, phase_3 & op_code[7])

    instruction_pointer.count((loaded != 0) & phase_4 & op_code[8])

    instruction_pointer.assign(loaded, phase_4 & op_code[9])

    index.assign(memory.get(op_address, phase_3 & op_code[10]), phase_3 & op_code[10])

    intermediate[0].iff_when(accumulator == loaded, phase_3 & op_code[11])
    accumulator[0].iff_when(intermediate[0], phase_4 & op_code[11])

    gt_or_eq = accumulator.greater_or_equal(loaded, phase_3 & op_code[12], list(carries))
    intermediate[0].iff_when(gt_or_eq, phase_3 & op_code[12])
    accumulator[0].iff_when(intermediate[0], phase_4 & op_code[12])

    bool_op_codes = [11, 12]
    for i in range(1, bit_width):
        accumulator[i].not_if(phase_4 & Bool.or_(*(op_code[code] for code in bool_op_codes)))

    phase.label("phase")
    instruction_pointer.label("instruction pointer")
    op_code.label("op code")
    op_address.label("op address")
    accumulator.label("accumulator")
    memory.index.label("mem index")
    memory.out.label("mem in")
    memory.out.label("mem out")
    intermediate.label("intermediate")
    freezer_bit.label("freezer")
    index.label("index")
    # [2:] to remove the accumulator and 0x01 which is reserved
    for i, section in enumerate(memory.mem_sections[2:]):
        section.label(f"mem section {i+2}")

    hardware.finish()
    hardware.output(r"D:\Programming\Programs\cssputer\index.html", r"D:\Programming\Programs\cssputer\puter.css")


if __name__ == '__main__':
    main()
