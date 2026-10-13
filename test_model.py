from app.ml.classifier import ExoplanetClassifier
classifier = ExoplanetClassifier()
print("Synthetic:", classifier.is_synthetic)
if not classifier.is_synthetic:
    print("Model loaded successfully!")
