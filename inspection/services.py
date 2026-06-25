"""
Inspection services — yuz aniqlash va geofencing yordamchi funksiyalari.
"""
import math
import numpy as np
import face_recognition


def calculate_cosine_similarity(embedding_a, embedding_b):
    """
    Ikki embedding orasidagi kosinus o'xshashligini hisoblash.
    """
    vector_a = np.asarray(embedding_a, dtype=float)
    vector_b = np.asarray(embedding_b, dtype=float)

    if vector_a.shape != vector_b.shape:
        return 0.0

    norm_a = np.linalg.norm(vector_a)
    norm_b = np.linalg.norm(vector_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(vector_a, vector_b) / (norm_a * norm_b))


def get_face_encoding(image_file):
    """
    Rasm faylidan yuz encoding (128 float) olish.
    Agar yuz topilmasa None qaytaradi.
    """
    # face_recognition kutubxonasi uchun numpy array kerak
    image = face_recognition.load_image_file(image_file)
    encodings = face_recognition.face_encodings(image)
    if not encodings:
        return None
    # Birinchi topilgan yuzning encoding'ini qaytarish
    return encodings[0].tolist()


def compare_faces(known_encoding, new_image_file, tolerance=0.45):
    """
    Saqlangan encoding bilan yangi rasmdagi yuzni solishtirish.
    Returns: (matched: bool, distance: float)
    Agar yangi rasmda yuz topilmasa -> (False, 999.0)
    """
    image = face_recognition.load_image_file(new_image_file)
    new_encodings = face_recognition.face_encodings(image)
    if not new_encodings:
        return False, 999.0

    known_array = np.array(known_encoding)
    new_array = np.array(new_encodings[0])

    # Evklid masofasi
    distance = float(np.linalg.norm(known_array - new_array))
    matched = distance <= tolerance
    return matched, distance


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Ikki nuqta orasidagi masofani metrda hisoblash (Haversine formulasi).
    """
    R = 6_371_000  # Yer radiusi metrda
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def is_inside_zone(user_lat, user_lon, zone):
    """
    Foydalanuvchi ish hududi ichida yoki tashqarisida ekanligini tekshirish.
    Returns: (inside: bool, distance: float)
    """
    distance = haversine_distance(user_lat, user_lon, zone.latitude, zone.longitude)
    inside = distance <= zone.radius_meters
    return inside, distance
