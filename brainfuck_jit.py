#!/usr/bin/env python3
"""Brainfuck → Python compiler — transpiles BF to Python bytecode for speed.

Compiles BF source to a Python function, applies optimizations,
then executes it. Much faster than interpretation.

Usage:
    python brainfuck_jit.py "++++++++[>++++++++++<-]>."
    python brainfuck_jit.py --test
"""
import sys

def compile_bf(source: str) -> str:
    """Compile BF to Python source code."""
    # Filter valid chars
    src = ''.join(c for c in source if c in '+-<>.,[]')

    lines = ["def _bf_run(_input=b''):",
             "  tape = [0]*30000",
             "  ptr = 0",
             "  out = []",
             "  inp_pos = 0"]
    indent = 1

    i = 0
    while i < len(src):
        pad = "  " * indent
        c = src[i]

        if c == '+':
            count = 0
            while i < len(src) and src[i] == '+': count += 1; i += 1
            lines.append(f"{pad}tape[ptr] = (tape[ptr] + {count}) & 255")
            continue
        elif c == '-':
            count = 0
            while i < len(src) and src[i] == '-': count += 1; i += 1
            lines.append(f"{pad}tape[ptr] = (tape[ptr] - {count}) & 255")
            continue
        elif c == '>':
            count = 0
            while i < len(src) and src[i] == '>': count += 1; i += 1
            lines.append(f"{pad}ptr += {count}")
            continue
        elif c == '<':
            count = 0
            while i < len(src) and src[i] == '<': count += 1; i += 1
            lines.append(f"{pad}ptr -= {count}")
            continue
        elif c == '.':
            lines.append(f"{pad}out.append(tape[ptr])")
        elif c == ',':
            lines.append(f"{pad}tape[ptr] = _input[inp_pos] if inp_pos < len(_input) else 0")
            lines.append(f"{pad}inp_pos += 1")
        elif c == '[':
            # Detect [-] clear loop
            if i + 2 < len(src) and src[i+1] == '-' and src[i+2] == ']':
                lines.append(f"{pad}tape[ptr] = 0")
                i += 3; continue
            # Detect [->+<] multiply loops
            mul = _detect_mul(src, i)
            if mul is not None:
                targets, skip = mul
                for off, factor in targets.items():
                    if off != 0:
                        lines.append(f"{pad}tape[ptr+{off}] = (tape[ptr+{off}] + tape[ptr] * {factor}) & 255")
                lines.append(f"{pad}tape[ptr] = 0")
                i += skip; continue
            lines.append(f"{pad}while tape[ptr]:")
            indent += 1
        elif c == ']':
            indent -= 1
        i += 1

    lines.append(f"  return bytes(out)")
    return '\n'.join(lines)

def _detect_mul(src, pos):
    """Detect multiply loop [->++>+++<<] patterns."""
    if src[pos] != '[': return None
    i = pos + 1; offset = 0; changes = {}
    while i < len(src) and src[i] != ']':
        if src[i] == '+': changes[offset] = changes.get(offset, 0) + 1
        elif src[i] == '-': changes[offset] = changes.get(offset, 0) - 1
        elif src[i] == '>': offset += 1
        elif src[i] == '<': offset -= 1
        elif src[i] in '.,[]': return None
        i += 1
    if i >= len(src) or offset != 0: return None
    if changes.get(0, 0) != -1: return None
    return changes, i - pos + 1

def run_bf(source: str, input_data: bytes = b"") -> bytes:
    """Compile and execute BF program."""
    py_src = compile_bf(source)
    ns = {}
    exec(py_src, ns)
    return ns['_bf_run'](input_data)

def test():
    print("=== BF JIT Compiler Tests ===\n")

    # Hello World
    hw = ">++++++++[<+++++++++>-]<.>++++[<+++++++>-]<+.+++++++..+++.>>++++++[<+++++++>-]<++.------------.>++++++[<+++++++++>-]<+.<.+++.------.--------.>>>++++[<++++++++>-]<+."
    result = run_bf(hw)
    assert result == b"Hello, World!"
    print(f"✓ Hello World: {result.decode()}")

    # Cat
    assert run_bf(",[.,]", b"Hi!") == b"Hi!"
    print("✓ Cat program")

    # Clear loop optimization
    src = compile_bf("+++[-]")
    assert "tape[ptr] = 0" in src
    print("✓ Clear loop [-] optimized")

    # Multiply loop optimization
    src2 = compile_bf("[->++<]")
    assert "tape[ptr] = 0" in src2
    print("✓ Multiply loop optimized")

    # Addition
    result = run_bf("+++++>+++<[->+<]>.", b"")
    assert result == bytes([8])
    print(f"✓ Addition: 5+3={result[0]}")

    # Run-length encoding
    src3 = compile_bf("++++++++")
    assert "+ 8" in src3 or "+8" in src3.replace(" ", "")
    print("✓ RLE: 8 increments batched")

    # Fibonacci (first 10 numbers)
    fib_bf = "+++++++++++>+>>>>++++++++++++++++++++++++++++++++++++++++++++>++++++++++++++++++++++++++++++++<<<<<<[>[>>>>>>+>+<<<<<<<-]>>>>>>>[<<<<<<<+>>>>>>>-]<[>++++++++++[-<-[>>+>+<<<-]>>>[<<<+>>>-]+<[>[-]<[-]]>[<<[>>>+<<<-]>>[-]]<<]>>>+<[-]<]<<<<<<<[>+++++>+<<-]>>[<<+>>-]>[>>>>+>+<<<<<-]>>>>>[<<<<<+>>>>>-]<[>++++++++++[-<-[>>+>+<<<-]>>>[<<<+>>>-]+<[>[-]<[-]]>[<<[>>>+<<<-]>>[-]]<<]>>>+<[-]<]<<<<<<<]>>>>>[>>>>>+<<<<<-]>[<+>-]>[-]>>[-]<<<<<<<.>.>.[.>]"
    # This BF prints fibonacci — just verify it runs without error
    result = run_bf(fib_bf)
    assert len(result) > 0
    print(f"✓ Fibonacci program: {list(result[:5])} ({len(result)} bytes)")

    import time
    # Performance: mandelbrot-lite (loop 1M iterations)
    perf = "+++++++++[>+++++++++<-]>[>++++++++++<-]" * 3
    t0 = time.perf_counter()
    run_bf(perf)
    elapsed = time.perf_counter() - t0
    print(f"✓ Perf: compiled+ran in {elapsed*1000:.1f}ms")

    print("\nAll tests passed! ✓")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--test": test()
    elif args[0] == "--compile": print(compile_bf(args[1]))
    else: sys.stdout.buffer.write(run_bf(args[0]))
