"""Pre-registration 17 (DRAFT until frozen): the registered analysis of pre-registration 15, unchanged, on the run of
Qwen2.5-Coder-32B-Instruct (analysis/modal_g/forks_17_modal.py), with one difference: a rule needs at least 25
complete states (40 in 15).

Usage: py -I -X utf8 analysis/analyze_17.py <run_dir> [--states analysis/fork_states_s/states.jsonl] [--gate]

The rows of this run have the format of the rows of 15 (the same runner apart from the model server's settings), so
analyze_15.main reads them as they are. Its lines that compare the prompt of arm S with the size logged for the same
step compare token counts of two tokenizers (this model's and Gemma's) and are not a check here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_15  # noqa: E402

MIN_COMPLETE = 25


def main():
    print('PRE-REGISTRATION 17: the design of pre-registration 15 on Qwen2.5-Coder-32B-Instruct (4-bit AWQ), '
          f'a model of another family; floor of complete states {MIN_COMPLETE} for each rule; the analysis below is '
          'that of pre-registration 15, unchanged otherwise')
    analyze_15.MIN_COMPLETE = MIN_COMPLETE      # read by analyze_15.main when it judges each rule
    analyze_15.main()


if __name__ == '__main__':
    main()
