# coding=utf-8
from __future__ import absolute_import
from __future__ import division

import ast
import argparse
import os

import numpy as np
import paddle
import paddle.jit
import paddle.static
from paddle.inference import Config, create_predictor
from paddlehub.module.module import moduleinfo, runnable, serving

from .data_feed import reader
from .processor import postprocess, base64_to_cv2


@moduleinfo(
    name="pyramidbox_face_detection",
    type="CV/face_detection",
    author="baidu-vis",
    author_email="",
    summary="Baidu's PyramidBox model for face detection.",
    version="1.2.0")
class PyramidBoxFaceDetection:
    def __init__(self):
        self.default_pretrained_model_path = os.path.join(self.directory, "pyramidbox_face_detection_widerface", "model")
        self._set_config()

    def _set_config(self):
        """
        predictor config setting
        """
        model = self.default_pretrained_model_path+'.pdmodel'
        params = self.default_pretrained_model_path+'.pdiparams'
        cpu_config = Config(model, params)
        cpu_config.disable_glog_info()
        cpu_config.disable_gpu()
        self.cpu_predictor = create_predictor(cpu_config)

        try:
            _places = os.environ["CUDA_VISIBLE_DEVICES"]
            int(_places[0])
            use_gpu = True
        except:
            use_gpu = False
        if use_gpu:
            gpu_config = Config(model, params)
            gpu_config.disable_glog_info()
            gpu_config.enable_use_gpu(memory_pool_init_size_mb=1000, device_id=0)
            self.gpu_predictor = create_predictor(gpu_config)

    def face_detection(self,
                       images=None,
                       paths=None,
                       data=None,
                       use_gpu=False,
                       output_dir='detection_result',
                       visualization=False,
                       score_thresh=0.15):
        """
        API for face detection.

        Args:
            images (list(numpy.ndarray)): images data, shape of each is [H, W, C]
            paths (list[str]): The paths of images.
            use_gpu (bool): Whether to use gpu.
            output_dir (str): The path to store output images.
            visualization (bool): Whether to save image or not.
            score_thresh (float): score threshold to limit the detection result.

        Returns:
            res (list[dict]): The result of face detection, keys are 'data' and 'path', the correspoding values are:
            data (list[dict]): 5 keys, where
                'left', 'top', 'right', 'bottom' are the coordinate of detection bounding box,
                'confidence' is the confidence this bbox.
            path (str): The path of original image.
        """
        if use_gpu:
            try:
                _places = os.environ["CUDA_VISIBLE_DEVICES"]
                int(_places[0])
            except:
                raise RuntimeError(
                    "Environment Variable CUDA_VISIBLE_DEVICES is not set correctly. If you wanna use gpu, please set CUDA_VISIBLE_DEVICES as cuda_device_id."
                )

        # compatibility with older versions
        if data:
            if 'image' in data:
                if paths is None:
                    paths = list()
                paths += data['image']

        res = list()
        # process one by one
        for element in reader(images, paths):
            image = np.expand_dims(element['image'], axis=0).astype('float32')
            predictor = self.gpu_predictor if use_gpu else self.cpu_predictor
            input_names = predictor.get_input_names()
            input_handle = predictor.get_input_handle(input_names[0])
            input_handle.copy_from_cpu(image)
            predictor.run()
            output_names = predictor.get_output_names()
            output_handle = predictor.get_output_handle(output_names[0])
            output = np.expand_dims(output_handle.copy_to_cpu(), axis=1)
            # print(len(data_out))  # 1
            out = postprocess(
                data_out=output_handle.copy_to_cpu(),
                org_im=element['org_im'],
                org_im_path=element['org_im_path'],
                org_im_width=element['org_im_width'],
                org_im_height=element['org_im_height'],
                output_dir=output_dir,
                visualization=visualization,
                score_thresh=score_thresh)
            res.append(out)
        return res

    @serving
    def serving_method(self, images, **kwargs):
        """
        Run as a service.
        """
        images_decode = [base64_to_cv2(image) for image in images]
        results = self.face_detection(images_decode, **kwargs)
        return results

    @runnable
    def run_cmd(self, argvs):
        """
        Run as a command.
        """
        self.parser = argparse.ArgumentParser(
            description="Run the {} module.".format(self.name),
            prog='hub run {}'.format(self.name),
            usage='%(prog)s',
            add_help=True)
        self.arg_input_group = self.parser.add_argument_group(title="Input options", description="Input data. Required")
        self.arg_config_group = self.parser.add_argument_group(
            title="Config options", description="Run configuration for controlling module behavior, not required.")
        self.add_module_config_arg()
        self.add_module_input_arg()
        args = self.parser.parse_args(argvs)
        results = self.face_detection(
            paths=[args.input_path],
            use_gpu=args.use_gpu,
            output_dir=args.output_dir,
            visualization=args.visualization,
            score_thresh=args.score_thresh)
        return results

    def add_module_config_arg(self):
        """
        Add the command config options.
        """
        self.arg_config_group.add_argument(
            '--use_gpu', type=ast.literal_eval, default=False, help="whether use GPU or not")
        self.arg_config_group.add_argument(
            '--output_dir', type=str, default='detection_result', help="The directory to save output images.")
        self.arg_config_group.add_argument(
            '--visualization', type=ast.literal_eval, default=False, help="whether to save output as images.")

    def add_module_input_arg(self):
        """
        Add the command input options.
        """
        self.arg_input_group.add_argument('--input_path', type=str, help="path to image.")
        self.arg_input_group.add_argument(
            '--score_thresh', type=ast.literal_eval, default=0.15, help="score threshold of face detection.")
