import os
from typing import List
from typing import Union

import numpy as np
import paddle
from paddle.utils import download
from paddle.vision.transforms import CenterCrop
from paddle.vision.transforms import Compose
from paddle.vision.transforms import Normalize
from paddle.vision.transforms import Resize
from paddle.vision.transforms import ToTensor

from .model import CLIP
from .model import TextTransformer
from .simple_tokenizer import SimpleTokenizer

__all__ = ['transform', 'tokenize', 'build_model']

MODEL_NAMES = ['VITL14']

URL = {'VITL14': os.path.join(os.path.dirname(__file__), 'pre_trained', 'vitl14_textencoder.pdparams')}

MEAN, STD = (0.48145466, 0.4578275, 0.40821073), (0.26862954, 0.26130258, 0.27577711)
_tokenizer = SimpleTokenizer()

transform = Compose([
    Resize(224, interpolation='bicubic'),
    CenterCrop(224), lambda image: image.convert('RGB'),
    ToTensor(),
    Normalize(mean=MEAN, std=STD), lambda t: t.unsqueeze_(0)
])


def tokenize(texts: Union[str, List[str]], context_length: int = 77):
    """
    Returns the tokenized representation of given input string(s)

    Parameters
    ----------
    texts : Union[str, List[str]]
        An input string or a list of input strings to tokenize

    context_length : int
        The context length to use; all CLIP models use 77 as the context length

    Returns
    -------
    A two-dimensional tensor containing the resulting tokens, shape = [number of input strings, context_length]
    """
    if isinstance(texts, str):
        texts = [texts]

    sot_token = _tokenizer.encoder["<|startoftext|>"]
    eot_token = _tokenizer.encoder["<|endoftext|>"]
    all_tokens = [[sot_token] + _tokenizer.encode(text) + [eot_token] for text in texts]
    result = paddle.zeros((len(all_tokens), context_length), dtype='int64')

    for i, tokens in enumerate(all_tokens):
        if len(tokens) > context_length:
            raise RuntimeError(f"Input {texts[i]} is too long for context length {context_length}")
        result[i, :len(tokens)] = paddle.to_tensor(np.array(tokens), dtype='int64')

    return result


def build_model(name='VITL14'):
    assert name in MODEL_NAMES, f"model name must be one of {MODEL_NAMES}"
    name2model = {'VITL14': build_vitl14_language_model}
    model = name2model[name]()
    weight = URL[name]
    sd = paddle.load(weight)
    state_dict = model.state_dict()
    for key, value in sd.items():
        if key in state_dict:
            state_dict[key] = value
    model.load_dict(state_dict)
    model.eval()
    return model


def build_vitl14_language_model():
    model = TextTransformer(context_length=77,
                            vocab_size=49408,
                            transformer_width=768,
                            transformer_heads=12,
                            transformer_layers=12)
    return model
