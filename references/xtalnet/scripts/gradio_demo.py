from pathlib import Path
import os
import gradio as gr
import numpy as np
import argparse


from eval_utils import get_eval_gradio, construct_input, get_model_gradio


def get_pxrd_2_crystal(text, eval_num, files):
    print(text)
    if files[-3:] != "txt":
        return "No correct file type"
    data = np.loadtxt(files)
    pxrd_x = data[:, 0]
    pxrd_y = data[:, 1]
    input_data = construct_input(text, pxrd_x, pxrd_y)

    out_path = get_eval_gradio(
        input_data, ccsg_model, cpcp_model, save_path, num_evals=int(eval_num)
    )

    return out_path


def upload_fn(file):
    return f"upload {os.path.basename(file)}"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--ccsg_ckpt_path",
    type=str,
    required=True,
    help="Path to the CCSG model checkpoint",
)
parser.add_argument(
    "--cpcp_ckpt_path",
    type=str,
    required=True,
    help="Path to the CPCP model checkpoint",
)
parser.add_argument(
    "--save_path",
    type=str,
    required=True,
    help="Path to save the output",
)
args = parser.parse_args()
ccsg_model, cpcp_model = get_model_gradio(args.ccsg_ckpt_path, args.cpcp_ckpt_path)
save_path = args.save_path
print("load model")

with gr.Blocks() as demo:
    with gr.Row():
        formula_input = gr.Textbox(label="Chemical Formula", value="Cu2H8C28N6O8")
        eval_num = gr.Slider(
            1,
            20,
            value=5,
            label="Number of Generation",
            info="Choose between 1 and 20",
            step=1,
        )
    desp = """## Upload A PXRD TXT File
Each line in the txt file should contain 2-theta value and its corresponding intensity, separated by a space.

The resolution for the 2-theta value should be set at 0.02.

example:
```
3.00 0.0011450092633350738
3.02 0.0011806625408974712
...
```
"""
    gr.Markdown(desp)
    upload_button = gr.UploadButton(
        "Click to Upload A TXT File", file_types=["text"], file_count="single"
    )
    upload_button.upload(upload_fn, inputs=upload_button, outputs=gr.Markdown())
    text_button = gr.Button("Click to Run Generation")
    file_output = gr.File()
    text_button.click(
        get_pxrd_2_crystal,
        inputs=[formula_input, eval_num, upload_button],
        outputs=file_output,
    )
demo.launch(share=True)