"""
services/ocr.py

Azure Document Intelligence (Form Recognizer) integration. Submits receipt
images to the prebuilt receipt model, polls for results, and transforms the
returned JSON into the application's internal receipt and line-item schema.
"""
