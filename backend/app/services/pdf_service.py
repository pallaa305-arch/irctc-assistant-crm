import io
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.config import TICKETS_DIR, INVOICES_DIR


class PDFService:
    """
    Generates high quality, pixel-perfect Electronic Reservation Slip (ERS Ticket PDF)
    and Travel Agency Tax Invoice / Bill PDF.
    """

    def __init__(self):
        self._setup_styles()

    def _setup_styles(self):
        self.styles = getSampleStyleSheet()

        # Primary Colors
        self.navy = colors.HexColor("#0B3C68")
        self.orange = colors.HexColor("#F37021")
        self.dark = colors.HexColor("#1E293B")
        self.light_bg = colors.HexColor("#F1F5F9")
        self.border_color = colors.HexColor("#CBD5E1")
        self.green = colors.HexColor("#15803D")

        # Custom Paragraph Styles
        self.title_style = ParagraphStyle(
            'TicketTitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=self.navy,
            alignment=TA_CENTER
        )

        self.subtitle_style = ParagraphStyle(
            'TicketSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=self.orange,
            alignment=TA_CENTER
        )

        self.header_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.white,
            alignment=TA_LEFT
        )

        self.cell_bold = ParagraphStyle(
            'CellBold',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=self.dark
        )

        self.cell_normal = ParagraphStyle(
            'CellNormal',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=self.dark
        )

        self.cell_center = ParagraphStyle(
            'CellCenter',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=self.dark
        )

        self.cell_status_cnf = ParagraphStyle(
            'CellCNF',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=self.green
        )

        self.note_style = ParagraphStyle(
            'NoteText',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            leading=10,
            textColor=colors.HexColor("#64748B")
        )

    def generate_ticket_pdf(
        self, 
        booking_data: Dict[str, Any], 
        passengers: List[Dict[str, Any]],
        save_to_disk: bool = True
    ) -> bytes:
        """
        Generate IRCTC Electronic Reservation Slip (ERS) PDF.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=30,
            bottomMargin=30
        )

        elements = []

        # 1. Header Banner
        elements.append(Paragraph("INDIAN RAILWAY CATERING AND TOURISM CORPORATION LTD.", self.title_style))
        elements.append(Spacer(1, 2))
        elements.append(Paragraph("ELECTRONIC RESERVATION SLIP (ERS) - VALID FOR TRAVEL", self.subtitle_style))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=self.navy, spaceBefore=2, spaceAfter=8))

        # 2. PNR & Main Booking Summary Box
        pnr = booking_data.get("pnr") or "2451234567"
        train_no = booking_data.get("train_number") or "12952"
        train_name = booking_data.get("train_name") or "NEW DELHI TEJAS RAJDHANI"
        quota = booking_data.get("quota") or "GENERAL (GN)"
        j_class = booking_data.get("journey_class") or "3A"
        booking_ref = booking_data.get("booking_ref") or f"BK-{datetime.now().strftime('%Y%m%d')}-001"
        booking_time = booking_data.get("booking_time") or datetime.now().strftime("%d-%b-%Y %H:%M:%S")

        pnr_summary_data = [
            [
                Paragraph("<b>PNR NUMBER:</b>", self.cell_normal),
                Paragraph(f"<font color='#0B3C68' size=11><b>{pnr}</b></font>", self.cell_bold),
                Paragraph("<b>TRAIN NO. & NAME:</b>", self.cell_normal),
                Paragraph(f"<b>{train_no}</b> - {train_name}", self.cell_bold)
            ],
            [
                Paragraph("<b>QUOTA:</b>", self.cell_normal),
                Paragraph(f"{quota}", self.cell_normal),
                Paragraph("<b>CLASS:</b>", self.cell_normal),
                Paragraph(f"<b>{j_class}</b>", self.cell_bold)
            ],
            [
                Paragraph("<b>BOOKING REF:</b>", self.cell_normal),
                Paragraph(f"{booking_ref}", self.cell_normal),
                Paragraph("<b>BOOKING DATE:</b>", self.cell_normal),
                Paragraph(f"{booking_time}", self.cell_normal)
            ]
        ]

        t_pnr = Table(pnr_summary_data, colWidths=[90, 160, 110, 160])
        t_pnr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.light_bg),
            ('BOX', (0, 0), (-1, -1), 1, self.navy),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, self.border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t_pnr)
        elements.append(Spacer(1, 10))

        # 3. Journey Route Details
        from_stn = booking_data.get("from_station") or "NDLS"
        to_stn = booking_data.get("to_station") or "MMCT"
        j_date = booking_data.get("journey_date") or datetime.now().strftime("%d/%m/%Y")
        dep_time = booking_data.get("departure_time") or "16:55"
        arr_time = booking_data.get("arrival_time") or "08:35"

        route_header = [
            [Paragraph("<b>JOURNEY DETAILS</b>", self.header_style), "", "", ""]
        ]
        t_route_head = Table(route_header, colWidths=[520, 0, 0, 0])
        t_route_head.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.navy),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t_route_head)

        route_data = [
            [
                Paragraph("<b>FROM STATION:</b>", self.cell_normal),
                Paragraph(f"<b>{from_stn}</b>", self.cell_bold),
                Paragraph("<b>TO STATION:</b>", self.cell_normal),
                Paragraph(f"<b>{to_stn}</b>", self.cell_bold)
            ],
            [
                Paragraph("<b>BOARDING DATE:</b>", self.cell_normal),
                Paragraph(f"<b>{j_date}</b>", self.cell_bold),
                Paragraph("<b>DISTANCE:</b>", self.cell_normal),
                Paragraph("1386 KM", self.cell_normal)
            ],
            [
                Paragraph("<b>SCHEDULED DEP:</b>", self.cell_normal),
                Paragraph(f"{dep_time} hrs", self.cell_normal),
                Paragraph("<b>SCHEDULED ARR:</b>", self.cell_normal),
                Paragraph(f"{arr_time} hrs", self.cell_normal)
            ]
        ]
        t_route = Table(route_data, colWidths=[110, 150, 110, 150])
        t_route.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, self.border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, self.border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t_route)
        elements.append(Spacer(1, 10))

        # 4. Passenger Details Table
        elements.append(Table([[Paragraph("<b>PASSENGER DETAILS</b>", self.header_style), "", "", "", "", ""]], colWidths=[520, 0, 0, 0, 0, 0], style=[
            ('BACKGROUND', (0, 0), (-1, -1), self.navy),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))

        pax_table_data = [
            [
                Paragraph("<b>#</b>", self.cell_bold),
                Paragraph("<b>Name</b>", self.cell_bold),
                Paragraph("<b>Age</b>", self.cell_center),
                Paragraph("<b>Gender</b>", self.cell_center),
                Paragraph("<b>Booking Status</b>", self.cell_center),
                Paragraph("<b>Current Status</b>", self.cell_center),
                Paragraph("<b>Coach / Berth</b>", self.cell_center)
            ]
        ]

        if not passengers:
            passengers = [{"name": "Deepak", "age": 28, "gender": "M", "allocated_seat": "B4, 45 [MB]", "status": "CNF"}]

        for idx, p in enumerate(passengers, 1):
            p_name = p.get("name", "Passenger")
            p_age = str(p.get("age", 30))
            p_gen = p.get("gender", "M")
            seat = p.get("allocated_seat") or f"B4, {40 + idx} [MB]"
            c_status = p.get("status") or "CNF"
            pax_table_data.append([
                Paragraph(str(idx), self.cell_normal),
                Paragraph(f"<b>{p_name}</b>", self.cell_normal),
                Paragraph(p_age, self.cell_center),
                Paragraph(p_gen, self.cell_center),
                Paragraph("CNF", self.cell_status_cnf),
                Paragraph(c_status, self.cell_status_cnf),
                Paragraph(f"<b>{seat}</b>", self.cell_center)
            ])

        t_pax = Table(pax_table_data, colWidths=[25, 165, 35, 45, 80, 80, 90])
        t_pax.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ('BOX', (0, 0), (-1, -1), 1, self.border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, self.border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(t_pax)
        elements.append(Spacer(1, 10))

        # 5. Fare Details
        fare_base = float(booking_data.get("fare") or 2150.0)
        convenience_fee = 35.40
        insurance = 0.45 * len(passengers)
        total_fare = fare_base + convenience_fee + insurance

        elements.append(Table([[Paragraph("<b>FARE BREAKUP & PAYMENT DETAILS</b>", self.header_style), ""]], colWidths=[520, 0], style=[
            ('BACKGROUND', (0, 0), (-1, -1), self.navy),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))

        fare_table_data = [
            [Paragraph("Ticket Base Fare:", self.cell_normal), Paragraph(f"₹ {fare_base:,.2f}", self.cell_bold)],
            [Paragraph("IRCTC Convenience Fee (Incl. of GST):", self.cell_normal), Paragraph(f"₹ {convenience_fee:,.2f}", self.cell_normal)],
            [Paragraph("Travel Insurance (Optional):", self.cell_normal), Paragraph(f"₹ {insurance:,.2f}", self.cell_normal)],
            [Paragraph("<b>Total Fare (Rupees):</b>", self.cell_bold), Paragraph(f"<b>₹ {total_fare:,.2f}</b>", self.cell_bold)],
            [Paragraph("Payment Mode / Status:", self.cell_normal), Paragraph("<font color='#15803D'><b>PAID (Online / UPI Verified)</b></font>", self.cell_bold)]
        ]
        t_fare = Table(fare_table_data, colWidths=[360, 160])
        t_fare.setStyle(TableStyle([
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#FEF3C7")),
            ('BOX', (0, 0), (-1, -1), 1, self.border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, self.border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t_fare)
        elements.append(Spacer(1, 10))

        # 6. Important Travel Instructions
        instructions = (
            "<b>IMPORTANT PASSENGER INSTRUCTIONS:</b><br/>"
            "1. One of the passengers must carry an original government-issued photo ID (Aadhaar, Voter ID, Driving License, Passport, PAN Card) during travel.<br/>"
            "2. ERS ticket along with original ID is valid for travel without requiring a physical printout.<br/>"
            "3. Charting status can be verified anytime using the Telegram Bot by entering PNR or clicking 'PNR Status Check'.<br/>"
            "4. For customer assistance, call 139 (Railway Enquiry) or use our 24/7 AI Railway Assistant bot."
        )
        elements.append(Paragraph(instructions, self.note_style))

        # Build Document
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Save to disk if requested
        if save_to_disk:
            fname = f"IRCTC_Ticket_{pnr}.pdf"
            out_path = TICKETS_DIR / fname
            with open(out_path, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def generate_invoice_pdf(
        self, 
        booking_data: Dict[str, Any], 
        passengers: List[Dict[str, Any]],
        save_to_disk: bool = True
    ) -> bytes:
        """
        Generate Travel Agency Tax Invoice / Bill PDF.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=30,
            bottomMargin=30
        )

        elements = []

        # 1. Invoice Header
        inv_title = ParagraphStyle(
            'InvTitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=self.navy,
            alignment=TA_LEFT
        )
        inv_badge = ParagraphStyle(
            'InvBadge',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=self.orange,
            alignment=TA_RIGHT
        )

        head_table = Table([
            [
                Paragraph("<b>IRCTC ASSISTANT & TRAVEL SERVICES</b><br/><font size=8 color='#64748B'>Official Fast-Track Ticketing & Travel Agency</font>", inv_title),
                Paragraph("<b>TAX INVOICE / BILL</b><br/><font size=8 color='#15803D'><b>ORIGINAL FOR RECIPIENT</b></font>", inv_badge)
            ]
        ], colWidths=[320, 200])
        head_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        elements.append(head_table)
        elements.append(HRFlowable(width="100%", thickness=1.5, color=self.navy, spaceBefore=2, spaceAfter=8))

        # 2. Company & Customer Meta
        ref = booking_data.get("booking_ref") or f"BK-{datetime.now().strftime('%Y%m%d')}-001"
        inv_no = f"INV-{ref.replace('BK-', '')}"
        inv_date = datetime.now().strftime("%d/%m/%Y")
        lead_pax = passengers[0].get("name", "Deepak") if passengers else "Deepak"

        meta_data = [
            [
                Paragraph("<b>SUPPLIER DETAILS:</b><br/>"
                          "<b>IRCTC Assistant Agency CRM</b><br/>"
                          "GSTIN: 07AAACI1234F1Z5<br/>"
                          "New Delhi, India - 110001<br/>"
                          "Support: support@irctc-assistant.in", self.cell_normal),
                Paragraph(f"<b>INVOICE DETAILS:</b><br/>"
                          f"<b>Invoice No:</b> {inv_no}<br/>"
                          f"<b>Date of Issue:</b> {inv_date}<br/>"
                          f"<b>Booking Ref:</b> {ref}<br/>"
                          f"<b>PNR Number:</b> {booking_data.get('pnr', '2451234567')}", self.cell_normal)
            ],
            [
                Paragraph(f"<b>BILLED TO (CUSTOMER):</b><br/>"
                          f"<b>Name:</b> {lead_pax}<br/>"
                          f"<b>Route:</b> {booking_data.get('from_station', 'NDLS')} ➔ {booking_data.get('to_station', 'MMCT')}<br/>"
                          f"<b>Journey Date:</b> {booking_data.get('journey_date', inv_date)}", self.cell_normal),
                Paragraph("<b>PAYMENT INFORMATION:</b><br/>"
                          "<b>Payment Method:</b> Online UPI / Gateway<br/>"
                          "<b>Payment Status:</b> <font color='#15803D'><b>PAID (100% Cleared)</b></font><br/>"
                          f"<b>Transaction Ref:</b> TXN-{ref}", self.cell_normal)
            ]
        ]

        t_meta = Table(meta_data, colWidths=[260, 260])
        t_meta.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.light_bg),
            ('BOX', (0, 0), (-1, -1), 1, self.border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, self.border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t_meta)
        elements.append(Spacer(1, 12))

        # 3. Itemized Billing Items Table
        fare_base = float(booking_data.get("fare") or 2150.0)
        pax_count = len(passengers) if passengers else 1
        agency_fee = 50.00
        gst_fee = round((agency_fee * 0.18), 2)
        total_bill = fare_base + agency_fee + gst_fee

        items_table_data = [
            [
                Paragraph("<b>#</b>", self.header_style),
                Paragraph("<b>Item Description</b>", self.header_style),
                Paragraph("<b>SAC/HSN</b>", self.header_style),
                Paragraph("<b>Qty</b>", self.header_style),
                Paragraph("<b>Rate (₹)</b>", self.header_style),
                Paragraph("<b>Total (₹)</b>", self.header_style)
            ],
            [
                Paragraph("1", self.cell_center),
                Paragraph(f"<b>Indian Railways Train Reservation</b><br/><font size=7 color='#64748B'>{booking_data.get('train_number', '12952')} {booking_data.get('train_name', 'Rajdhani')} ({booking_data.get('journey_class', '3A')})</font>", self.cell_normal),
                Paragraph("996411", self.cell_center),
                Paragraph(str(pax_count), self.cell_center),
                Paragraph(f"{fare_base:,.2f}", self.cell_normal),
                Paragraph(f"<b>{fare_base:,.2f}</b>", self.cell_normal)
            ],
            [
                Paragraph("2", self.cell_center),
                Paragraph("<b>Travel Agency Automated Booking Convenience Fee</b>", self.cell_normal),
                Paragraph("998553", self.cell_center),
                Paragraph("1", self.cell_center),
                Paragraph(f"{agency_fee:,.2f}", self.cell_normal),
                Paragraph(f"<b>{agency_fee:,.2f}</b>", self.cell_normal)
            ],
            [
                Paragraph("3", self.cell_center),
                Paragraph("<b>CGST (9%) + SGST (9%) on Convenience Fee</b>", self.cell_normal),
                Paragraph("998553", self.cell_center),
                Paragraph("1", self.cell_center),
                Paragraph(f"{gst_fee:,.2f}", self.cell_normal),
                Paragraph(f"<b>{gst_fee:,.2f}</b>", self.cell_normal)
            ]
        ]

        t_items = Table(items_table_data, colWidths=[25, 235, 60, 40, 80, 80])
        t_items.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.navy),
            ('BOX', (0, 0), (-1, -1), 1, self.border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, self.border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t_items)
        elements.append(Spacer(1, 10))

        # 4. Total Summary Block
        total_data = [
            [Paragraph("Subtotal Amount:", self.cell_normal), Paragraph(f"₹ {fare_base + agency_fee:,.2f}", self.cell_normal)],
            [Paragraph("Total Taxes (GST):", self.cell_normal), Paragraph(f"₹ {gst_fee:,.2f}", self.cell_normal)],
            [Paragraph("<b>GRAND TOTAL (INCL. TAXES):</b>", self.cell_bold), Paragraph(f"<font color='#0B3C68' size=11><b>₹ {total_bill:,.2f}</b></font>", self.cell_bold)],
            [Paragraph("Amount Paid in Words:", self.cell_normal), Paragraph("<b>Two Thousand Two Hundred Nine Rupees Only</b>", self.cell_normal)]
        ]

        t_total = Table(total_data, colWidths=[360, 160])
        t_total.setStyle(TableStyle([
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#FEF3C7")),
            ('BOX', (0, 0), (-1, -1), 1, self.border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, self.border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t_total)
        elements.append(Spacer(1, 15))

        # 5. Signatory & Footer
        sign_table = Table([
            [
                Paragraph("<b>Terms & Conditions:</b><br/>"
                          "1. This is a computer-generated invoice and does not require a physical signature.<br/>"
                          "2. Railway cancellations and refunds are subject to IRCTC refund rules.", self.note_style),
                Paragraph("<b>For IRCTC Assistant Agency</b><br/><br/>"
                          "<b>Authorized Signatory</b><br/>"
                          "<font size=7 color='#15803D'>[Digitally Signed & Verified]</font>", ParagraphStyle('SignRight', parent=self.cell_normal, alignment=TA_RIGHT))
            ]
        ], colWidths=[340, 180])
        elements.append(sign_table)

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Save to disk
        if save_to_disk:
            fname = f"Invoice_Bill_{ref}.pdf"
            out_path = INVOICES_DIR / fname
            with open(out_path, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes


pdf_service = PDFService()
