# src/backend/api/routes/export_pdf.py

import os
import sys
import base64
import io
from datetime import datetime
from typing import Optional
from enum import Enum

# --- Path setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# --- FastAPI ---
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

# --- ReportLab PDF generation ---
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib import colors
from PIL import Image as PILImage

# --- Project-specific imports ---
from backend.core.startup import shared_resources
from backend.artifact_model.RequirementModel import RequirementModel
from backend.artifact_model.RequirementClassification import RequirementClassification, RequirementsClassificationList
from backend.artifact_model.SystemRequirement import SystemRequirement, SystemRequirementsList
from backend.artifact_model.SoftwareRequirementSpecs import SoftwareRequirementSpecs
from backend.artifact_model.shared import RequirementCategory, RequirementPriority
router = APIRouter()

# Pydantic model for export request
class ExportPDFRequest(BaseModel):
    artifact_id: str
    thread_id: str


def create_pdf_for_artifact(artifact_data: dict) -> bytes:
    """
    Generate a PDF from artifact data.

    Args:
        artifact_data: Dictionary containing artifact information including:
            - type: artifact type
            - content: artifact content (Pydantic model data)
            - id: artifact ID
            - version: artifact version
            - agent: creating agent
            - timestamp: creation timestamp

    Returns:
        bytes: PDF file content
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)

    # Container for PDF elements
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=12,
        spaceBefore=12
    )
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#555555'),
        spaceAfter=6
    )
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )

    # Extract artifact info
    artifact_type = artifact_data.get('type', 'Unknown')
    artifact_id = artifact_data.get('id', 'N/A')
    artifact_version = artifact_data.get('version', 'N/A')
    agent = artifact_data.get('agent', 'N/A')
    timestamp = artifact_data.get('timestamp', 'N/A')
    content = artifact_data.get('content', {})

    # Title
    type_labels = {
        'requirements_classification': 'Requirements Classification',
        'system_requirements': 'System Requirements List',
        'requirements_model': 'Requirements Model',
        'software_requirement_specs': 'Software Requirement Specifications'
    }
    title = type_labels.get(artifact_type, artifact_type.replace('_', ' ').title())
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 12))

    # Metadata
    metadata_text = f"<b>Artifact ID:</b> {artifact_id}<br/>"
    metadata_text += f"<b>Version:</b> {artifact_version}<br/>"
    metadata_text += f"<b>Created by:</b> {agent}<br/>"
    metadata_text += f"<b>Timestamp:</b> {timestamp}<br/>"
    elements.append(Paragraph(metadata_text, normal_style))
    elements.append(Spacer(1, 20))

    # Content based on artifact type
    if artifact_type == 'requirements_classification':
        _add_requirements_classification_content(elements, content, heading_style, subheading_style, normal_style)
    elif artifact_type == 'system_requirements':
        _add_system_requirements_content(elements, content, heading_style, subheading_style, normal_style)
    elif artifact_type == 'requirements_model':
        _add_requirements_model_content(elements, content, heading_style, subheading_style, normal_style)
    elif artifact_type == 'software_requirement_specs':
        _add_srs_content(elements, content, heading_style, subheading_style, normal_style)
    else:
        # Generic content rendering
        elements.append(Paragraph("Content", heading_style))
        elements.append(Paragraph(str(content), normal_style))

    # Build PDF
    doc.build(elements)

    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def _add_requirements_classification_content(elements, content, heading_style, subheading_style, normal_style):
    """Add requirements classification content to PDF"""
    elements.append(Paragraph("Requirements Classification", heading_style))

    if content.get('summary'):
        elements.append(Paragraph(f"<i>{content['summary']}</i>", normal_style))
        elements.append(Spacer(1, 12))

    req_list = content.get('req_class_id', [])

    for idx, req in enumerate(req_list, 1):
        # Create a colored box for each requirement
        req_id = req.get('requirement_id', 'N/A')
        req_text = req.get('requirement_text', 'N/A')
        category = req.get('category', 'N/A').value
        priority = req.get('priority', 'N/A').value

        elements.append(Paragraph(f"<b>{req_id}</b>", subheading_style))
        elements.append(Paragraph(req_text, normal_style))

        # Metadata table - 2 rows for better spacing
        data = [
            ['Category:', category],
            ['Priority:', priority]
        ]
        t = Table(data, colWidths=[1.5*inch, 4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 16))


def _add_system_requirements_content(elements, content, heading_style, subheading_style, normal_style):
    """Add system requirements content to PDF"""
    elements.append(Paragraph("System Requirements List", heading_style))

    if content.get('summary'):
        elements.append(Paragraph(f"<i>{content['summary']}</i>", normal_style))
        elements.append(Spacer(1, 12))

    srl = content.get('srl', [])

    for idx, req in enumerate(srl, 1):
        req_id = req.get('requirement_id', 'N/A')
        req_statement = req.get('requirement_statement', 'N/A')
        category = req.get('category', 'N/A').value
        priority = req.get('priority', 'N/A').value

        elements.append(Paragraph(f"<b>{req_id}</b>", subheading_style))
        elements.append(Paragraph(req_statement, normal_style))

        # Metadata table - 2 rows for better spacing
        data = [
            ['Category:', category],
            ['Priority:', priority]
        ]
        t = Table(data, colWidths=[1.5*inch, 4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 16))


def _add_requirements_model_content(elements, content, heading_style, subheading_style, normal_style):
    """Add requirements model content to PDF - including diagram"""
    elements.append(Paragraph("Requirements Model", heading_style))

    if content.get('summary'):
        elements.append(Paragraph(f"<i>{content['summary']}</i>", normal_style))
        elements.append(Spacer(1, 12))

    # Add diagram if available
    diagram_base64 = content.get('diagram_base64')
    if diagram_base64:
        try:
            elements.append(Paragraph("Use Case Diagram", subheading_style))

            # Decode base64 image
            img_data = base64.b64decode(diagram_base64)
            img_buffer = io.BytesIO(img_data)

            # Open with PIL to get dimensions
            pil_img = PILImage.open(img_buffer)
            img_width, img_height = pil_img.size

            # Calculate scaling to fit page width (max 6 inches)
            max_width = 6 * inch
            max_height = 8 * inch

            aspect = img_height / float(img_width)
            if img_width > max_width:
                img_width = max_width
                img_height = img_width * aspect

            if img_height > max_height:
                img_height = max_height
                img_width = img_height / aspect

            # Reset buffer and create ReportLab Image
            img_buffer.seek(0)
            img = Image(img_buffer, width=img_width, height=img_height)
            elements.append(img)
            elements.append(Spacer(1, 12))
        except Exception as e:
            elements.append(Paragraph(f"Error loading diagram: {str(e)}", normal_style))
            elements.append(Spacer(1, 12))

    # Add PlantUML code
    uml_content = content.get('uml_fmt_content')
    if uml_content:
        elements.append(Paragraph("PlantUML Code", subheading_style))
        # Format code with monospace style
        code_style = ParagraphStyle(
            'Code',
            parent=normal_style,
            fontName='Courier',
            fontSize=8,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=6,
            spaceAfter=12,
            backColor=colors.HexColor('#f5f5f5')
        )
        # Split into lines and add each as paragraph
        for line in uml_content.split('\n'):
            elements.append(Paragraph(line.replace('<', '&lt;').replace('>', '&gt;'), code_style))


def _add_srs_content(elements, content, heading_style, subheading_style, normal_style):
    """Add Software Requirement Specs content to PDF"""
    elements.append(Paragraph("Software Requirement Specifications", heading_style))

    if content.get('summary'):
        elements.append(Paragraph(f"<i>{content['summary']}</i>", normal_style))
        elements.append(Spacer(1, 20))

    # Brief Introduction
    if content.get('brief_introduction'):
        elements.append(Paragraph("Brief Introduction", subheading_style))
        elements.append(Paragraph(content['brief_introduction'], normal_style))
        elements.append(Spacer(1, 12))

    # Product Description
    if content.get('product_description'):
        elements.append(Paragraph("Product Description", subheading_style))
        elements.append(Paragraph(content['product_description'], normal_style))
        elements.append(Spacer(1, 12))

    # Functional Requirements
    if content.get('functional_requirements'):
        elements.append(Paragraph("Functional Requirements", subheading_style))
        # Handle multiline text
        for line in content['functional_requirements'].split('\n'):
            if line.strip():
                elements.append(Paragraph(line, normal_style))
        elements.append(Spacer(1, 12))

    # Non-Functional Requirements
    if content.get('non_functional_requirements'):
        elements.append(Paragraph("Non-Functional Requirements", subheading_style))
        for line in content['non_functional_requirements'].split('\n'):
            if line.strip():
                elements.append(Paragraph(line, normal_style))
        elements.append(Spacer(1, 12))

    # References
    if content.get('references'):
        elements.append(Paragraph("References", subheading_style))
        for line in content['references'].split('\n'):
            if line.strip():
                elements.append(Paragraph(line, normal_style))
        elements.append(Spacer(1, 12))


@router.post("/graph/export_pdf")
async def export_artifact_as_pdf(request: ExportPDFRequest):
    """
    Export an artifact as PDF

    Args:
        request: ExportPDFRequest with artifact_id and thread_id

    Returns:
        PDF file as bytes with proper content-type header
    """
    thread_id = request.thread_id
    artifact_id = request.artifact_id

    # Check if graph is available
    if 'graph' not in shared_resources or shared_resources['graph'] is None:
        raise HTTPException(
            status_code=503,
            detail="The graph application is not available or has not been initialized."
        )

    graph = shared_resources['graph']
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Get current state
        current_state = await graph.aget_state(config)

        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail="Thread state not found")

        # Find the artifact in state
        artifacts = current_state.values.get('artifacts', [])
        target_artifact = None

        for artifact in artifacts:
            if artifact.id == artifact_id:
                target_artifact = artifact
                break

        if not target_artifact:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found in thread {thread_id}")

        # Prepare artifact data for PDF generation
        artifact_data = {
            'id': target_artifact.id,
            'type': target_artifact.content_type.value if hasattr(target_artifact.content_type, 'value') else str(target_artifact.content_type),
            'version': target_artifact.version,
            'agent': target_artifact.created_by.value if hasattr(target_artifact.created_by, 'value') else str(target_artifact.created_by),
            'timestamp': target_artifact.timestamp.isoformat() if hasattr(target_artifact.timestamp, 'isoformat') else str(target_artifact.timestamp),
            'content': target_artifact.content.model_dump() if hasattr(target_artifact.content, 'model_dump') else {}
        }

        # Generate PDF
        pdf_bytes = create_pdf_for_artifact(artifact_data)

        # Create filename
        filename = f"{artifact_id}.pdf"

        # Return PDF as response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error exporting artifact as PDF: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to export artifact: {str(e)}")
