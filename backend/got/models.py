from django.db import models

# Create your models here.
class OrderForm(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255)
    order_type = models.OneToOneField("order.OrderType", verbose_name=("Order Type"), on_delete=models.CASCADE)
    structure = models.JSONField()

    def __str__(self):
        return self.name if self.name else "OrderForm ID {}".format(self.id)
    
class OrderFormSubmission(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order_report = models.OneToOneField("order.OrderReport", verbose_name=("Order Report"), on_delete=models.CASCADE)
    filled_form = models.JSONField()

    def __str__(self):
        return "Submission for Order Report ID {}".format(self.order_report.id)