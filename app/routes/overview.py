from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
from app.decorators import role_required
from app.extensions import db
from app.models.member import Member
from app.models.visitor import Visitor
from app.models.giving import Giving
from app.models.check_in import CheckIn
from app.models.sms_log import SMSLog
from app.utils import normalize_sa_phone
import csv
from io import StringIO, BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from app.utils.branching import branch_query, enforce_branch_access
from sqlalchemy import func, or_


overview_bp = Blueprint("overview", __name__, url_prefix="/overview")


@overview_bp.route("/", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def search():

    if request.method == "POST":

        phone = normalize_sa_phone(request.form.get("phone"))

        if not phone:
            flash("Invalid phone number.", "error")
            return redirect(url_for("overview.search"))

        return redirect(url_for("overview.profile", phone=phone))

    return render_template("overview_search.html")


@overview_bp.route("/<phone>")
@login_required
@role_required("super_admin", "admin")
def profile(phone):

    from app.utils.branching import branch_query, enforce_branch_access
    from sqlalchemy import func

    member = branch_query(Member).filter_by(phone=phone).first()
    visitor = branch_query(Visitor).filter_by(phone=phone).first()

    person = member or visitor

    if not person:
        flash("No record found.", "error")
        return redirect(url_for("overview.search"))

    enforce_branch_access(person)

    person_type = "Member" if member else "Visitor"

    if member:
        # FIXED: Include giving linked by member_id OR matching phone number
        # This shows "Unknown" giving records that were made before member registration
        raw_giving = (
            branch_query(Giving)
            .filter(
                or_(
                    Giving.member_id == member.id,
                    Giving.phone == phone
                )
            )
            .with_entities(
                func.to_char(Giving.created_at, 'YYYY-MM'),
                func.sum(Giving.amount)
            )
            .group_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .order_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .all()
        )

        attendance_history = (
            branch_query(CheckIn)
            .filter(CheckIn.member_id == member.id)
            .order_by(CheckIn.created_at.desc())
            .all()
        )
    else:
        # FIXED: Include giving linked by visitor_id OR matching phone number
        raw_giving = (
            branch_query(Giving)
            .filter(
                or_(
                    Giving.visitor_id == visitor.id,
                    Giving.phone == phone
                )
            )
            .with_entities(
                func.to_char(Giving.created_at, 'YYYY-MM'),
                func.sum(Giving.amount)
            )
            .group_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .order_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .all()
        )

        attendance_history = (
            branch_query(CheckIn)
            .filter(CheckIn.visitor_id == visitor.id)
            .order_by(CheckIn.created_at.desc())
            .all()
        )

    sms_history = SMSLog.query.filter_by(phone=phone)\
        .order_by(SMSLog.created_at.desc()).all()

    monthly_giving = [
        {"month": m, "total": float(t)}
        for m, t in raw_giving
    ]

    return render_template(
        "overview_profile.html",
        person=person,
        person_type=person_type,
        monthly_giving=monthly_giving,
        attendance_history=attendance_history,
        sms_history=sms_history
    )


@overview_bp.route("/<phone>/export")
@login_required
@role_required("super_admin", "admin")
def export_profile(phone):
    """Export individual overview data as CSV"""
    
    member = branch_query(Member).filter_by(phone=phone).first()
    visitor = branch_query(Visitor).filter_by(phone=phone).first()
    person = member or visitor

    if not person:
        flash("No record found.", "error")
        return redirect(url_for("overview.search"))

    enforce_branch_access(person)

    person_type = "Member" if member else "Visitor"
    
    from sqlalchemy import func

    # Get data (FIXED: include phone-matched giving)
    if member:
        raw_giving = (
            branch_query(Giving)
            .with_entities(
                func.to_char(Giving.created_at, 'YYYY-MM'),
                func.sum(Giving.amount)
            )
            .filter(
                or_(
                    Giving.member_id == member.id,
                    Giving.phone == phone
                )
            )
            .group_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .order_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .all()
        )
        attendance_history = CheckIn.query.filter_by(member_id=member.id)\
            .order_by(CheckIn.created_at.desc()).all()
    else:
        raw_giving = (
            db.session.query(
                func.to_char(Giving.created_at, 'YYYY-MM'),
                func.sum(Giving.amount)
            )
            .filter(
                or_(
                    Giving.visitor_id == visitor.id,
                    Giving.phone == phone
                )
            )
            .group_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .order_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .all()
        )
        attendance_history = CheckIn.query.filter_by(visitor_id=visitor.id)\
            .order_by(CheckIn.created_at.desc()).all()

    sms_history = SMSLog.query.filter_by(phone=phone)\
        .order_by(SMSLog.created_at.desc()).all()

    # Create CSV
    si = StringIO()
    writer = csv.writer(si)
    
    # Write person details
    writer.writerow(["Individual Overview Report"])
    writer.writerow([])
    writer.writerow(["Name", f"{person.first_name} {getattr(person, 'last_name', '')}"])
    writer.writerow(["Type", person_type])
    writer.writerow(["Phone", phone])
    writer.writerow([])
    
    # Write monthly giving summary
    writer.writerow(["Monthly Giving Summary"])
    writer.writerow(["Month", "Total Given"])
    for month, total in raw_giving:
        writer.writerow([month, f"R {float(total):.2f}"])
    writer.writerow([])
    
    # Write attendance history
    writer.writerow(["Attendance History"])
    writer.writerow(["Date", "Service"])
    for checkin in attendance_history:
        service_name = checkin.service.name if hasattr(checkin, 'service') and checkin.service else "N/A"
        writer.writerow([
            checkin.check_in_date.strftime("%Y-%m-%d") if checkin.check_in_date else "N/A",
            service_name
        ])
    writer.writerow([])
    
    # Write SMS history
    writer.writerow(["SMS History"])
    writer.writerow(["Date", "Message", "Status"])
    for sms in sms_history:
        writer.writerow([
            sms.created_at.strftime("%Y-%m-%d") if sms.created_at else "N/A",
            sms.message,
            sms.status
        ])

    output = si.getvalue()
    
    # Generate filename
    safe_name = f"{person.first_name}_{getattr(person, 'last_name', '')}".replace(" ", "_")
    filename = f"overview_{safe_name}_{phone}.csv"
    
    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@overview_bp.route("/<phone>/export-pdf")
@login_required
@role_required("super_admin", "admin")
def export_profile_pdf(phone):
    """Export individual overview data as PDF"""
    
    member = Member.query.filter_by(phone=phone).first()
    visitor = Visitor.query.filter_by(phone=phone).first()
    person = member or visitor

    if not person:
        flash("No record found.", "error")
        return redirect(url_for("overview.search"))

    person_type = "Member" if member else "Visitor"
    full_name = f"{person.first_name} {getattr(person, 'last_name', '')}"
    
    from sqlalchemy import func

    # Get data (FIXED: include phone-matched giving)
    if member:
        raw_giving = (
            branch_query(Giving)
            .with_entities(
                func.to_char(Giving.created_at, 'YYYY-MM'),
                func.sum(Giving.amount)
            )
            .filter(
                or_(
                    Giving.member_id == member.id,
                    Giving.phone == phone
                )
            )
            .group_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .order_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .all()
        )

        attendance_history = (
            branch_query(CheckIn)
            .filter(CheckIn.member_id == member.id)
            .order_by(CheckIn.created_at.desc())
            .all()
        )
    else:
        raw_giving = (
            db.session.query(
                func.to_char(Giving.created_at, 'YYYY-MM'),
                func.sum(Giving.amount)
            )
            .filter(
                or_(
                    Giving.visitor_id == visitor.id,
                    Giving.phone == phone
                )
            )
            .group_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .order_by(func.to_char(Giving.created_at, 'YYYY-MM'))
            .all()
        )
        attendance_history = CheckIn.query.filter_by(visitor_id=visitor.id)\
            .order_by(CheckIn.created_at.desc()).all()

    sms_history = SMSLog.query.filter_by(phone=phone)\
        .order_by(SMSLog.created_at.desc()).all()

    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    
    # Container for elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=20,
        alignment=1  # Center alignment
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=15
    )
    normal_style = styles["Normal"]
    
    # Title
    elements.append(Paragraph("Individual Overview Report", title_style))
    elements.append(Spacer(1, 20))
    
    # Personal Details Section
    elements.append(Paragraph("Personal Details", section_style))
    
    personal_data = [
        ["Name:", full_name],
        ["Type:", person_type],
        ["Phone:", phone]
    ]
    
    personal_table = Table(personal_data, colWidths=[100, 350])
    personal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(personal_table)
    elements.append(Spacer(1, 15))
    
    # Monthly Giving Summary
    elements.append(Paragraph("Monthly Giving Summary", section_style))
    
    giving_data = [["Month", "Total Given"]]
    for month, total in raw_giving:
        giving_data.append([month, f"R {float(total):.2f}"])
    
    if len(giving_data) == 1:
        giving_data.append(["No records", "R 0.00"])
    
    giving_table = Table(giving_data, colWidths=[225, 225])
    giving_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(giving_table)
    elements.append(Spacer(1, 15))
    
    # Attendance History
    elements.append(Paragraph("Attendance History", section_style))
    
    attendance_data = [["Date", "Service"]]
    for checkin in attendance_history:
        service_name = checkin.service.name if hasattr(checkin, 'service') and checkin.service else "N/A"
        date_str = checkin.check_in_date.strftime("%Y-%m-%d") if checkin.check_in_date else "N/A"
        attendance_data.append([date_str, service_name])
    
    if len(attendance_data) == 1:
        attendance_data.append(["No records", "-"])
    
    attendance_table = Table(attendance_data, colWidths=[150, 300])
    attendance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(attendance_table)
    elements.append(Spacer(1, 15))
    
    # SMS History
    elements.append(Paragraph("SMS History", section_style))
    
    sms_data = [["Date", "Message", "Status"]]
    for sms in sms_history:
        date_str = sms.created_at.strftime("%Y-%m-%d") if sms.created_at else "N/A"
        # Truncate message if too long
        message = sms.message[:50] + "..." if len(sms.message) > 50 else sms.message
        sms_data.append([date_str, message, sms.status])
    
    if len(sms_data) == 1:
        sms_data.append(["No records", "-", "-"])
    
    sms_table = Table(sms_data, colWidths=[80, 280, 90])
    sms_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9b59b6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(sms_table)
    
    # Footer
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )
    from datetime import datetime
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", footer_style))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Generate filename
    safe_name = full_name.replace(" ", "_")
    filename = f"overview_{safe_name}_{phone}.pdf"
    
    return Response(
        buffer,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )