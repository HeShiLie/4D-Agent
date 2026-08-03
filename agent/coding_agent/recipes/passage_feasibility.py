"""Recipe: Passage Feasibility — compare gate width to vehicle width.

Task pattern: Vehicle approaching a cone gate, determine if it can pass.
Key technique: HSV orange detection for cones, frame-diff for vehicle, compute gap/width ratio.
"""
import numpy as np


def solve(ctx):
    ORANGE = [((5, 180, 150), (22, 255, 255))]
    frames = ctx.get_frames(n=20, scale=0.5)

    # Detect cones in each frame
    cone_detections = []
    for idx, fr in frames:
        blobs = ctx.perception.detect_blobs(fr, ORANGE, min_area=60)
        tall_blobs = [b for b in blobs if b["bbox"][3] > b["bbox"][2] * 0.9]
        cone_detections.append((idx, tall_blobs))

    # Find frame with most cones (likely the gate frame)
    best_frame = max(cone_detections, key=lambda x: len(x[1]))
    cones = best_frame[1]

    if len(cones) < 2:
        return EvidenceBundle(
            execution_status="partial",
            warnings=["Could not detect at least 2 cones"],
            observations=[Observation(
                name="cone_count", value=len(cones), confidence=0.5,
                supporting_frames=[best_frame[0]], method="HSV orange detection"
            )]
        )

    # Gate gap = distance between two nearest cone centroids
    centroids = [c["centroid"] for c in cones]
    min_gap = float("inf")
    for i, a in enumerate(centroids):
        for b in centroids[i+1:]:
            d = np.hypot(a[0] - b[0], a[1] - b[1])
            if d < min_gap:
                min_gap = d

    # Vehicle width from frame differencing
    vehicle_widths = []
    for i in range(1, len(frames)):
        fr1 = frames[i-1][1]
        fr2 = frames[i][1]
        diff = cv2.absdiff(fr1, fr2)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 28, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, np.ones((9, 9), np.uint8))
        # Mask out cone regions
        for c in cones:
            x, y, w, h = c["bbox"]
            cv2.rectangle(thresh, (x-4, y-4), (x+w+4, y+h+4), 0, -1)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            largest = max(cnts, key=cv2.contourArea)
            if cv2.contourArea(largest) > 3000:
                _, _, w, _ = cv2.boundingRect(largest)
                vehicle_widths.append(w)

    vehicle_width = max(vehicle_widths) if vehicle_widths else None
    margin_ratio = (min_gap / vehicle_width) if (vehicle_width and min_gap < float("inf")) else None

    measurements = [
        Measurement(name="gate_gap_px", value=float(min_gap), unit="px", method="cone pair distance"),
    ]
    if vehicle_width:
        measurements.append(Measurement(name="vehicle_width_px", value=float(vehicle_width), unit="px", method="frame-diff largest blob"))
    if margin_ratio:
        measurements.append(Measurement(name="margin_ratio", value=margin_ratio, unit="ratio", method="gap/width"))

    observations = [
        Observation(
            name="passage_feasibility",
            value="likely_pass" if margin_ratio and margin_ratio > 1.3 else
                  "likely_fail" if margin_ratio and margin_ratio < 1.0 else "uncertain",
            confidence=0.8 if margin_ratio and (margin_ratio > 1.5 or margin_ratio < 0.8) else 0.5,
            supporting_frames=[best_frame[0]],
            method="gap/width ratio threshold"
        )
    ]

    return EvidenceBundle(
        execution_status="success" if margin_ratio else "partial",
        observations=observations,
        measurements=measurements,
        limitations=["Image-space measurement, no metric calibration"]
    )
