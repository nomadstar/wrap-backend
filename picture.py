import cv2

def capture_image_from_camera(camera_index=0, output_file='captured_image.jpg'):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("No se pudo abrir la cámara.")
        return

    ret, frame = cap.read()
    if ret:
        cv2.imwrite(output_file, frame)
        print(f"Imagen guardada como {output_file}")
    else:
        print("No se pudo capturar la imagen.")

    cap.release()

if __name__ == "__main__":
    # Cambia el índice de la cámara si tienes más de una (0, 1, 2, ...)
    capture_image_from_camera(camera_index=1, output_file='ganache/captured_image.jpg')