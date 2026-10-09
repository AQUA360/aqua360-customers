1. GET /got/orders/{order_id}/form/
   ← Returns OrderForm.structure

2. For each photo field:
   POST /got/orders/{order_id}/upload-form-photo/
   Body: multipart/form-data { file, field_token: "foto_anterior" }
   
   Backend:
   - Uploads directly with entity="ORDER", entity_id=order.id
   - Returns { document_id, url, field_token }
   
   Storage path:
   /media/documents/ORDER_FORM_PHOTO/ORDER/2025/ORDER_FORM_PHOTO_DECEMBER/foto_anterior_uuid.jpg

3. POST /got/orders/{order_id}/add-report/
   Body: {
     "start_at": "11:05",
     "end_at": "13:05",
     "filled_form": [
       { "token": "foto_anterior", "response": 45 },      // document_id
       { "token": "codi_anterior", "response": "ABC123" } // text value
     ]
   }
   
   Backend (in transaction):
   a) Validate filled_form against OrderForm.structure
   b) Create OrderReport
   c) Create OrderFormSubmission (filled_form JSON stores document_ids for photos)
   d) Update photo documents: entity_id = order_report.id (optional, for better linking)
   
   If error at any step:
   - Rollback transaction
   - Delete uploaded documents (by document_ids from filled_form)