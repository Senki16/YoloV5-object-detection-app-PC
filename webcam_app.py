import argparse
import os

import cv2
import torch


def parse_args():
    parser = argparse.ArgumentParser(description="YOLOv5 webcam object detection app")
    parser.add_argument("--weights", type=str, default="yolov5s.pt", help="model weights path")
    parser.add_argument("--source", type=str, default="0", help="webcam source index or video file path")
    parser.add_argument("--imgsz", type=int, nargs="+", default=[640, 640], help="inference size h,w")
    parser.add_argument("--conf-thres", type=float, default=0.25, help="confidence threshold")
    parser.add_argument("--iou-thres", type=float, default=0.45, help="NMS IoU threshold")
    parser.add_argument("--device", default="", help="cuda device, i.e. 0 or cpu")
    return parser.parse_args()


def main():
    args = parse_args()

    source = args.source
    if source.isdigit():
        source = int(source)

    # Load the YOLOv5 model from the local repository
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    model = torch.hub.load(repo_dir, "yolov5s", source="local")
    model.conf = args.conf_thres
    model.iou = args.iou_thres
    model.classes = None
    model.to(args.device if args.device else "cpu")

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video source: {args.source}")

    window_name = "YOLOv5 Webcam"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        success, frame = cap.read()
        if not success:
            print("Failed to read frame from source.")
            break

        # Run inference
        results = model(frame, size=args.imgsz)

        # Draw boxes and labels on the image
        detections = results.xyxy[0]
        for *box, conf, cls in detections.tolist():
            x1, y1, x2, y2 = map(int, box)
            label = f"{results.names[int(cls)]}: {conf:.2f}"
            color = (0, 255, 0)  # Green box

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Setup text properties
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            # Calculate text position (above the box, or inside if too close to top)
            y_text = y1 - 10 if y1 - 10 > text_height else y1 + text_height + 10

            # Draw text background
            cv2.rectangle(frame, (x1, y_text - text_height - 5), (x1 + text_width, y_text + baseline - 5), color, -1)

            # Draw text
            cv2.putText(
                frame,
                label,
                (x1, y_text - 5),
                font,
                font_scale,
                (0, 0, 0),  # Black text for better contrast against green
                thickness,
                cv2.LINE_AA,
            )
        cv2.imshow(window_name, frame)

        if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
