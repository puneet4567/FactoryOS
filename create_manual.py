from reportlab.pdfgen import canvas
import os

print("📄 creating manual.pdf for testing...")
c = canvas.Canvas("manual.pdf")
c.drawString(100, 750, "FACTORY OPERATING MANUAL - CONFIDENTIAL")
c.drawString(100, 730, "---------------------------------------")
c.drawString(100, 700, "Error 404: Network Timeout. Solution: Restart Router.")
c.drawString(100, 680, "Error 502: Blade Jam caused by debris. Solution: Apply grease to the main axle and clear debris.")
c.drawString(100, 660, "Error 999: Overheating. Solution: Turn off machine for 10 minutes.")
c.save()
print("✅ Created valid 'manual.pdf'")
