TASKS = [
    {
        "id": "iso",
        "label": "ISO",
        "title": "ISO and Image Brightness",
        "info": (
            "ISO controls the camera sensor's sensitivity to light. It helps "
            "determine how bright or dark the image will appear."
        ),
        "instruction": "Adjust the ISO to make the image bright enough without making it too grainy.",
        "options": [100, 200, 400, 800, 1600, 3200],
        "target": 800,
        "start": 100,
        "format": lambda v: str(v),
        "final_feedback": "Good brightness and clear image.",
    },
    {
        "id": "aperture",
        "label": "Aperture",
        "title": "Aperture and Exposure",
        "info": (
            "Aperture is the adjustable opening in the lens that controls how much "
            "light enters the camera. A lower f-number means a wider opening and a "
            "brighter image."
        ),
        "instruction": "Adjust the aperture (f-stop) to correct the image's exposure.",
        "options": [4, 5.6, 8, 11],
        "target": 4,
        "start": 11,
        "format": lambda v: f"f/{v}",
        "final_feedback": "Image is clear with good background.",
    },
    {
        "id": "shutter",
        "label": "Shutter Speed",
        "title": "Shutter Speed and Motion",
        "info": (
            "Shutter speed is how long the sensor is exposed to light. Slower "
            "shutter speeds let in more light but can blur moving subjects."
        ),
        "instruction": "Adjust the shutter speed to correct the exposure while keeping the image sharp.",
        "options": [8, 15, 30, 60, 125, 250, 500, 1000],
        "target": 60,
        "start": 500,
        "format": lambda v: f"1/{v}",
        "final_feedback": "Image is sharp and clear.",
    },
    {
        "id": "wb",
        "label": "White Balance",
        "title": "White Balance and Color",
        "info": (
            "White balance corrects the color tone of an image so that whites look "
            "neutral under different lighting conditions."
        ),
        "instruction": "Change the white balance preset so the colors look natural under the current lighting.",
        "options": ["Auto", "Daylight", "Cloudy", "Tungsten", "Fluorescent"],
        "target": "Tungsten",
        "start": "Auto",
        "format": lambda v: v,
        "final_feedback": "Colors look natural.",
    },
]

DEFAULTS = {"iso": 400, "aperture": 5.6, "shutter": 60, "wb": "Auto"}

# Tasks captured by remotely triggering the DSLR's shutter and transferring the result,
# instead of a continuous live USB preview (see README "Live preview and the D3500's
# blackout issue").
REMOTE_CAPTURE_TASK_IDS = frozenset({"iso"})


def uses_remote_capture(task_id: str) -> bool:
    return task_id in REMOTE_CAPTURE_TASK_IDS

GRADE_LABEL = {
    "A": "Congratulations!",
    "B": "Good Job!",
    "C": "Not Bad!",
    "D": "Keep Practicing!",
}


def compute_grade(total: int) -> str:
    if total <= 6:
        return "A"
    if total <= 14:
        return "B"
    if total <= 24:
        return "C"
    return "D"


def fresh_task_state():
    return [
        {
            "value": t["start"],
            "baseline": False,
            "checked": False,
            "correct": False,
            "retries": 0,
            "captureStatus": "idle",
            "captureError": None,
        }
        for t in TASKS
    ]


def correct_message(task: dict) -> str:
    return {
        "iso": "Good ISO setting, image brightness is balanced.",
        "aperture": "Good aperture setting, exposure looks balanced.",
        "shutter": "Good shutter speed, exposure and sharpness look balanced.",
        "wb": "Good white balance, colors look natural.",
    }[task["id"]]


def incorrect_message(task: dict, cur_idx: int, target_idx: int) -> str:
    task_id = task["id"]
    if task_id == "iso":
        return (
            "Image is too dark. Raise the ISO setting."
            if cur_idx < target_idx
            else "Image is too bright! Lower the ISO setting."
        )
    if task_id == "aperture":
        return "Image is too dark. Use a lower f-number to open the aperture."
    if task_id == "shutter":
        return (
            "Image is too dark. Use a slower shutter speed."
            if cur_idx > target_idx
            else "Image looks blurry. Use a faster shutter speed."
        )
    if task_id == "wb":
        return "Image still looks too warm/orange. Select the Tungsten preset to match the lighting."
    raise ValueError(f"unknown task id: {task_id}")
