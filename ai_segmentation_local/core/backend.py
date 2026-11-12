import os
import urllib.request

SAM_CHECKPOINT_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
SAM_CHECKPOINT_NAME = "sam_vit_b_01ec64.pth"

CLIP_MODEL = "ViT-B-32"
CLIP_PRETRAINED = "laion2b_s34b_b88k"

CLIP_POSITIVE_TEMPLATES = [
    "an aerial photo of {}",
    "a satellite image of {}",
    "a drone photo of {}",
    "a photo of {}",
]
CLIP_NEGATIVE_TEMPLATES = [
    "an aerial photo of something else",
    "a satellite image of something else",
    "a drone photo of something else",
    "a photo of something else",
]


class LocalBackend:
    """Fully local segmentation backend.

    SAM (Segment Anything, open weights) produces masks; CLIP (open weights)
    scores each mask crop against the free-text label typed by the user.
    No network call is made at inference time: models are downloaded once,
    from public URLs, on first use.
    """

    def __init__(self, plugin_dir, progress=None):
        self.plugin_dir = plugin_dir
        self.progress = progress or (lambda _msg: None)
        self._sam = None
        self._predictor = None
        self._mask_generator = None
        self._clip_model = None
        self._clip_preprocess = None
        self._clip_tokenizer = None
        self._clip_text_features = None

    def _ensure_checkpoint(self):
        models_dir = os.path.join(self.plugin_dir, "models")
        os.makedirs(models_dir, exist_ok=True)
        path = os.path.join(models_dir, SAM_CHECKPOINT_NAME)
        if os.path.exists(path) and os.path.getsize(path) > 100_000_000:
            return path
        self.progress("Downloading SAM model, ~375 MB, once, free open weights...")
        tmp = path + ".part"
        urllib.request.urlretrieve(SAM_CHECKPOINT_URL, tmp)
        os.replace(tmp, path)
        return path

    def _load_sam(self):
        if self._sam is not None:
            return
        from segment_anything import (
            SamAutomaticMaskGenerator,
            SamPredictor,
            sam_model_registry,
        )

        self._sam = sam_model_registry["vit_b"](checkpoint=self._ensure_checkpoint())
        self._sam.to("cpu")
        self._predictor = SamPredictor(self._sam)
        self._mask_generator = SamAutomaticMaskGenerator(
            self._sam,
            points_per_side=24,
            pred_iou_thresh=0.75,
            stability_score_thresh=0.88,
            crop_n_layers=1,
            min_mask_region_area=64,
        )

    def _load_clip(self):
        if self._clip_model is not None:
            return
        import torch
        import open_clip

        self.progress("Downloading CLIP model, ~350 MB, once, free open weights...")
        model, _, preprocess = open_clip.create_model_and_transforms(
            CLIP_MODEL, pretrained=CLIP_PRETRAINED
        )
        model.eval()
        self._clip_model = model
        self._clip_preprocess = preprocess
        self._clip_tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
        texts = [
            t.format("{}") for t in CLIP_POSITIVE_TEMPLATES
        ] + CLIP_NEGATIVE_TEMPLATES
        with torch.no_grad():
            tokens = self._clip_tokenizer(texts)
            feats = model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        self._clip_text_features = feats
        self._clip_n_positive = len(CLIP_POSITIVE_TEMPLATES)

    def segment_points(self, image_rgb, points, point_labels):
        """Return a boolean mask for the given positive/negative points."""
        import numpy as np

        self._load_sam()
        self._predictor.set_image(image_rgb)
        masks, scores, _logits = self._predictor.predict(
            point_coords=np.asarray(points, dtype=np.float32),
            point_labels=np.asarray(point_labels, dtype=np.int64),
            multimask_output=True,
        )
        return masks[int(np.argmax(scores))]

    def detect_label(self, image_rgb, label, max_side=1536, score_threshold=0.55):
        """Detect every object matching `label` in the image.

        Returns a list of {"mask", "score", "iou"} dicts, best first, where
        mask is a boolean array with the shape of `image_rgb`.
        """
        import cv2
        import numpy as np
        import torch
        from PIL import Image

        self._load_sam()
        self._load_clip()

        h, w = image_rgb.shape[:2]
        scale = min(1.0, max_side / float(max(h, w)))
        if scale < 1.0:
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            small = cv2.resize(image_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            small = image_rgb

        self.progress("Proposing masks with SAM (local)...")
        proposals = self._mask_generator.generate(small)
        if not proposals:
            return []

        pos_templates = [t.format(label) for t in CLIP_POSITIVE_TEMPLATES]
        neg_templates = list(CLIP_NEGATIVE_TEMPLATES)
        texts = pos_templates + neg_templates
        with torch.no_grad():
            tokens = self._clip_tokenizer(texts)
            text_feats = self._clip_model.encode_text(tokens)
            text_feats = text_feats / text_feats.norm(dim=-1, keepdim=True)

        results = []
        for m in proposals:
            seg = m["segmentation"]
            if int(seg.sum()) < 64:
                continue
            x, y, bw, bh = [int(v) for v in m["bbox"]]
            crop = small[max(0, y):y + bh, max(0, x):x + bw]
            if crop.size == 0:
                continue
            pil = Image.fromarray(crop).convert("RGB")
            with torch.no_grad():
                img_in = self._clip_preprocess(pil).unsqueeze(0)
                img_feat = self._clip_model.encode_image(img_in)
                img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
                logits = (100.0 * img_feat @ text_feats.T).squeeze(0)
                probs = logits.softmax(dim=-1)
            score = float(probs[: len(pos_templates)].mean().item())
            if score < score_threshold:
                continue
            if scale < 1.0:
                up = cv2.resize(
                    seg.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST
                )
                full_mask = up > 0
            else:
                full_mask = seg
            results.append(
                {
                    "mask": full_mask,
                    "score": score,
                    "iou": float(m.get("predicted_iou", 0.0)),
                }
            )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results
