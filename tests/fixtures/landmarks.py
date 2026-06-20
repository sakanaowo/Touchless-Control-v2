from touchless_control.contracts import HandFrame, Point3D


def _landmarks() -> tuple[Point3D, ...]:
    return tuple((index / 20.0, index / 40.0, 0.0) for index in range(21))


def stable_pointing_hand(*, timestamp_ms: int) -> HandFrame:
    return HandFrame(
        timestamp_ms=timestamp_ms,
        image_width=640,
        image_height=480,
        landmarks_img=_landmarks(),
        landmarks_world=_landmarks(),
        handedness="right",
        detection_confidence=0.95,
        presence_confidence=0.96,
        tracking_confidence=0.97,
    )


def tracking_lost_hand(*, timestamp_ms: int) -> HandFrame:
    return HandFrame(
        timestamp_ms=timestamp_ms,
        image_width=640,
        image_height=480,
        landmarks_img=_landmarks(),
        landmarks_world=_landmarks(),
        handedness="right",
        detection_confidence=0.42,
        presence_confidence=0.20,
        tracking_confidence=0.18,
    )
