#include <lib/gui/elistbox.h>
#include <lib/gui/elistboxcontent.h>
#include <lib/gdi/epoint.h>
#include <lib/gdi/font.h>
#include <lib/python/python.h>
#include <lib/gdi/epng.h>
#include <lib/base/nconfig.h>
#include <sstream>

using namespace std;

/*
	The basic idea is to have an interface which gives all relevant list
	processing functions, and can be used by the listbox to browse trough
	the list.

	The listbox directly uses the implemented cursor. It tries hard to avoid
	iterating trough the (possibly very large) list, so it should be O(1),
	i.e. the performance should not be influenced by the size of the list.

	The list interface knows how to draw the current entry to a specified
	offset. Different interfaces can be used to adapt different lists,
	pre-filter lists on the fly etc.

		cursorSave/Restore is used to avoid re-iterating the list on redraw.
		The current selection is always selected as cursor position, the
	cursor is then positioned to the start, and then iterated. This gives
	at most 2x m_items_per_page cursor movements per redraw, indepenent
	of the size of the list.

	Although cursorSet is provided, it should be only used when there is no
	other way, as it involves iterating trough the list.
 */

iListboxContent::~iListboxContent()
{
}

iListboxContent::iListboxContent() : m_listbox(0)
{
}

void iListboxContent::setListbox(eListbox *lb)
{
	m_listbox = lb;
	m_listbox->setOrientation(getOrientation());
	m_listbox->setItemHeight(getItemHeight());
	m_listbox->setItemWidth(getItemWidth());
}

int iListboxContent::currentCursorSelectable()
{
	return 1;
}

//////////////////////////////////////

DEFINE_REF(eListboxPythonStringContent);

eListboxPythonStringContent::eListboxPythonStringContent()
	: m_saved_cursor_line(0), m_cursor(0), m_saved_cursor(0), m_itemheight(25), m_itemwidth(25), m_orientation(1)
{
}

eListboxPythonStringContent::~eListboxPythonStringContent()
{
	Py_XDECREF(m_list);
}

void eListboxPythonStringContent::cursorHome()
{
	m_cursor = 0;
}

void eListboxPythonStringContent::cursorEnd()
{
	m_cursor = size();
}

int eListboxPythonStringContent::cursorMove(int count)
{
	m_cursor += count;

	if (m_cursor < 0)
		cursorHome();
	else if (m_cursor > size())
		cursorEnd();
	return 0;
}

int eListboxPythonStringContent::cursorValid()
{
	return m_cursor < size();
}

int eListboxPythonStringContent::cursorSet(int n)
{
	m_cursor = n;

	if (m_cursor < 0)
		cursorHome();
	else if (m_cursor > size())
		cursorEnd();
	return 0;
}

int eListboxPythonStringContent::cursorGet()
{
	return m_cursor;
}

int eListboxPythonStringContent::currentCursorSelectable()
{
	if (m_list && cursorValid())
	{
		ePyObject item = PyList_GET_ITEM(m_list, m_cursor);
		if (!PyTuple_Check(item))
			return 1;
		if (PyTuple_Size(item) >= 2)
			return 1;
	}
	return 0;
}

void eListboxPythonStringContent::cursorSave()
{
	m_saved_cursor = m_cursor;
}

void eListboxPythonStringContent::cursorRestore()
{
	m_cursor = m_saved_cursor;
}

void eListboxPythonStringContent::cursorSaveLine(int line)
{
	m_saved_cursor_line = line;
}

int eListboxPythonStringContent::cursorRestoreLine()
{
	return m_saved_cursor_line;
}

int eListboxPythonStringContent::size()
{
	if (!m_list)
		return 0;
	return PyList_Size(m_list);
}

void eListboxPythonStringContent::setSize(const eSize &size)
{
	m_itemsize = size;
}

void eListboxPythonStringContent::paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected)
{
	ePtr<gFont> fnt;
	bool validitem = (m_list && cursorValid());
	eListboxStyle *local_style = 0;
	bool cursorValid = this->cursorValid();
	bool itemZoomed;
	gRGB border_color;
	int border_size = 0;
	ePoint offs = offset;
	ePoint zoomoffs = offset;
	eRect itemRect(offset, m_itemsize);

	/* get local listbox style, if present */
	if (m_listbox)
		local_style = m_listbox->getLocalStyle();

	if (local_style)
	{
		border_size = local_style->m_border_size;
		border_color = local_style->m_border_color;
		itemZoomed = local_style->m_selection_zoom > 1.0;

		if (selected && itemZoomed && local_style->is_set.zoom_content)
			fnt = local_style->m_font_zoomed;
		else
			fnt = local_style->m_font;

		if (selected && itemZoomed)
		{
			itemRect = eRect(offs, eSize(local_style->m_selection_width, local_style->m_selection_height));
			if (local_style->is_set.zoom_move_content)
			{
				zoomoffs = ePoint(offset.x() - (((local_style->m_selection_width) - m_itemsize.width()) / 4), offset.y() - (((local_style->m_selection_height) - m_itemsize.height()) / 4));
			}
		}
		else if (!selected && itemZoomed)
		{
			offs = ePoint(offset.x() + (((local_style->m_selection_width) - m_itemsize.width()) / 2), offset.y() + (((local_style->m_selection_height) - m_itemsize.height()) / 2));
			zoomoffs = offs;
			itemRect = eRect(offs, m_itemsize);
		}
		painter.clip(itemRect);
		style.setStyle(painter, selected ? eWindowStyle::styleListboxSelected : eWindowStyle::styleListboxNormal);

		if (selected)
		{
			/* if we have a local background color set, use that. */
			if (local_style->is_set.background_color_selected)
				painter.setBackgroundColor(local_style->m_background_color_selected);
			/* same for foreground */
			if (local_style->is_set.foreground_color_selected)
				painter.setForegroundColor(local_style->m_foreground_color_selected);
		}
		else
		{
			/* if we have a local background color set, use that. */
			if (local_style->is_set.background_color)
				painter.setBackgroundColor(local_style->m_background_color);
			/* same for foreground */
			if (local_style->is_set.foreground_color)
				painter.setForegroundColor(local_style->m_foreground_color);
		}
	}
	else
	{
		painter.clip(itemRect);
		style.setStyle(painter, selected ? eWindowStyle::styleListboxSelected : eWindowStyle::styleListboxNormal);
	}

	if (!fnt)
	{
		style.getFont(eWindowStyle::fontListbox, fnt);
		if (selected && local_style && local_style->is_set.zoom_content)
		{
			if (fnt)
				m_font_zoomed = new gFont(fnt->family, fnt->pointSize * local_style->m_selection_zoom);
			fnt = m_font_zoomed;
		}
	}

	int orientation = (m_listbox) ? m_listbox->getOrientation() : 1;

	/* if we have no transparent background */
	if (!local_style || !local_style->is_set.transparent_background)
	{
		/* blit background picture, if available (otherwise, clear only) */
		if (local_style && local_style->m_background && cursorValid)
		{
			if (validitem)
			{
				int x = offs.x();
				int y = offs.y();
				x += (orientation & 2) ? (itemRect.width() - local_style->m_background->size().width()) / 2 : 0;   // vertical
				y += (orientation & 1) ? (itemRect.height() - local_style->m_background->size().height()) / 2 : 0; // horizontal
				painter.blit(local_style->m_background, ePoint(x, y), eRect(), 0);
			}
		}
		else if (local_style->is_set.background_gradient_color && !local_style->m_background && cursorValid)
			painter.drawGradient(itemRect, local_style->m_background_gradient_color_start, local_style->m_background_gradient_color_end, local_style->m_background_color_gradient_direction, local_style->m_background_color_gradient_flag);
		else
			painter.clear();
	}
	else
	{
		if (local_style->m_background && cursorValid)
		{
			if (validitem)
			{
				int x = offs.x();
				int y = offs.y();
				x += (orientation & 2) ? (itemRect.width() - local_style->m_background->size().width()) / 2 : 0;   // vertical
				y += (orientation & 1) ? (itemRect.height() - local_style->m_background->size().height()) / 2 : 0; // horizontal
				painter.blit(local_style->m_background, ePoint(x, y), eRect(), gPainter::BT_ALPHATEST);
			}
		}
		else if (local_style->is_set.background_gradient_color && !local_style->m_background && cursorValid)
			painter.drawGradient(itemRect, local_style->m_background_gradient_color_start, local_style->m_background_gradient_color_end, local_style->m_background_color_gradient_direction, local_style->m_background_color_gradient_flag);
		else if (selected && !local_style->m_selection)
			painter.clear();
	}
	// Draw frame here so to be under the content
	if (selected && (!local_style || !local_style->m_selection) && (!local_style || !local_style->is_set.border))
		style.drawFrame(painter, eRect(offs, itemRect.size()), eWindowStyle::frameListboxEntry);

	if (validitem)
	{
		int gray = 0;
		ePyObject item = PyList_GET_ITEM(m_list, m_cursor); // borrowed reference!
		painter.setFont(fnt);

		/* the user can supply tuples, in this case the first one will be displayed. */
		if (PyTuple_Check(item))
		{
			if (PyTuple_Size(item) == 1)
				gray = 1;
			item = PyTuple_GET_ITEM(item, 0);
		}

		if (selected && local_style && local_style->m_selection)
		{
			int x = offs.x();
			int y = offs.y();
			x += (orientation & 2) ? (itemRect.width() - local_style->m_selection->size().width()) / 2 : 0;	  // vertical
			y += (orientation & 1) ? (itemRect.height() - local_style->m_selection->size().height()) / 2 : 0; // horizontal
			painter.blit(local_style->m_selection, ePoint(x, y), eRect(), gPainter::BT_ALPHATEST);
		}
		else if (selected && local_style->is_set.background_gradient_selected_color && !local_style->m_selection)
			painter.drawGradient(itemRect, local_style->m_background_gradient_color_selected_start, local_style->m_background_gradient_color_selected_end, local_style->m_background_color_gradient_selected_direction, local_style->m_background_color_gradient_selected_flag);

		if (!item || item == Py_None)
		{
			/* Please Note .. this needs to fixed in the navigation code because this separator can be selected as an active element*/
			/* seperator */
			int half_height = itemRect.height() / 2;
			int half_width = itemRect.width() / 2;
			if (orientation == 1)
				painter.fill(eRect(offs.x() + half_height, offs.y() + half_height - 2, itemRect.width() - itemRect.height(), 4));
			if (orientation == 2)
				painter.fill(eRect(offs.x() + half_width, offs.y() + half_width - 2, itemRect.width() - itemRect.height(), 4));
		}
		else
		{
			const char *string = PyString_Check(item) ? PyString_AsString(item) : "<not-a-string>";
			ePoint text_offset = zoomoffs;
			if (gray)
				painter.setForegroundColor(gRGB(0x808080));

			int flags = 0;
			if (local_style)
			{
				text_offset += local_style->m_text_padding.topLeft();
				// VTI workaround
				if (local_style->is_set.use_vti_workaround)
					text_offset += local_style->m_text_padding.topLeft();

				if (local_style->m_valign == eListboxStyle::alignTop)
					flags |= gPainter::RT_VALIGN_TOP;
				else if (local_style->m_valign == eListboxStyle::alignCenter)
					flags |= gPainter::RT_VALIGN_CENTER;
				else if (local_style->m_valign == eListboxStyle::alignBottom)
					flags |= gPainter::RT_VALIGN_BOTTOM;

				if (local_style->m_halign == eListboxStyle::alignLeft)
					flags |= gPainter::RT_HALIGN_LEFT;
				else if (local_style->m_halign == eListboxStyle::alignCenter)
					flags |= gPainter::RT_HALIGN_CENTER;
				else if (local_style->m_halign == eListboxStyle::alignRight)
					flags |= gPainter::RT_HALIGN_RIGHT;
				else if (local_style->m_halign == eListboxStyle::alignBlock)
					flags |= gPainter::RT_HALIGN_BLOCK;

				int paddingx = local_style->m_text_padding.x();
				int paddingy = local_style->m_text_padding.y();
				int paddingw = local_style->m_text_padding.width();
				int paddingh = local_style->m_text_padding.height();

				auto position = eRect(text_offset.x(), text_offset.y(), itemRect.width() - (paddingx * 2) - paddingw, itemRect.height() - (paddingy * 2) - paddingh);

				painter.renderText(position, string, flags, border_color, border_size);
			}
			else
			{
				painter.renderText(eRect(text_offset, itemRect.size()), string, flags, border_color, border_size);
			}
		}
	}

	painter.clippop();
}

void eListboxPythonStringContent::setList(ePyObject list)
{
	Py_XDECREF(m_list);
	if (!PyList_Check(list))
	{
		m_list = ePyObject();
	}
	else
	{
		m_list = list;
		Py_INCREF(m_list);
	}

	if (m_listbox)
		m_listbox->entryReset(false);
}

void eListboxPythonStringContent::setOrientation(int orientation)
{
	m_orientation = orientation;
	if (m_listbox)
	{
		m_listbox->setOrientation(orientation);
	}
}

void eListboxPythonStringContent::setItemHeight(int height)
{
	m_itemheight = height;
	if (m_listbox)
		m_listbox->setItemHeight(height);
}

void eListboxPythonStringContent::setItemWidth(int width)
{
	m_itemwidth = width;
	if (m_listbox)
		m_listbox->setItemWidth(width);
}

PyObject *eListboxPythonStringContent::getCurrentSelection()
{
	if (!(m_list && cursorValid()))
		Py_RETURN_NONE;

	ePyObject r = PyList_GET_ITEM(m_list, m_cursor);
	Py_XINCREF(r);
	return r;
}

void eListboxPythonStringContent::invalidateEntry(int index)
{
	if (m_listbox)
		m_listbox->entryChanged(index);
}

void eListboxPythonStringContent::invalidate()
{
	if (m_listbox)
	{
		int s = size();
		if (m_cursor >= s)
			m_listbox->moveSelectionTo(s ? s - 1 : 0);
		else
			m_listbox->invalidate();
	}
}

//////////////////////////////////////

RESULT SwigFromPython(ePtr<gPixmap> &res, PyObject *obj);

void eListboxPythonConfigContent::paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected)
{
	ePtr<gFont> fnt;
	ePtr<gFont> fnt2;
	eRect itemrect(offset, m_itemsize);
	eListboxStyle *local_style = 0;
	bool cursorValid = this->cursorValid();
	gRGB border_color;
	int border_size = 0;

	painter.clip(itemrect);
	style.setStyle(painter, selected ? eWindowStyle::styleListboxSelected : eWindowStyle::styleListboxNormal);

	/* get local listbox style, if present */
	if (m_listbox)
		local_style = m_listbox->getLocalStyle();

	if (local_style)
	{
		border_size = local_style->m_border_size;
		border_color = local_style->m_border_color;
		fnt = local_style->m_font;
		fnt2 = local_style->m_valuefont;
		if (selected)
		{
			/* if we have a local background color set, use that. */
			if (local_style->is_set.background_color_selected)
				painter.setBackgroundColor(local_style->m_background_color_selected);
			/* same for foreground */
			if (local_style->is_set.foreground_color_selected)
				painter.setForegroundColor(local_style->m_foreground_color_selected);
		}
		else
		{
			/* if we have a local background color set, use that. */
			if (local_style->is_set.background_color)
				painter.setBackgroundColor(local_style->m_background_color);
			/* same for foreground */
			if (local_style->is_set.foreground_color)
				painter.setForegroundColor(local_style->m_foreground_color);
		}
	}

	if (!fnt)
		style.getFont(eWindowStyle::fontEntry, fnt);

	if (!fnt2)
		style.getFont(eWindowStyle::fontValue, fnt2);

	int orientation = (m_listbox) ? m_listbox->getOrientation() : 1;

	if (!local_style || !local_style->is_set.transparent_background)
	/* if we have no transparent background */
	{
		/* blit background picture, if available (otherwise, clear only) */
		if (local_style && local_style->m_background && cursorValid)
		{
			int x = offset.x();
			int y = offset.y();
			x += (orientation & 2) ? (m_itemsize.width() - local_style->m_background->size().width()) / 2 : 0;	 // vertical
			y += (orientation & 1) ? (m_itemsize.height() - local_style->m_background->size().height()) / 2 : 0; // horizontal
			painter.blit(local_style->m_background, ePoint(x, y), eRect(), 0);
		}
		else if (local_style && local_style->is_set.background_gradient_color && !local_style->m_background && cursorValid)
			painter.drawGradient(itemrect, local_style->m_background_gradient_color_start, local_style->m_background_gradient_color_end, local_style->m_background_color_gradient_direction, local_style->m_background_color_gradient_flag);
		else
			painter.clear();
	}
	else
	{
		if (local_style->m_background && cursorValid)
		{
			int x = offset.x();
			int y = offset.y();
			x += (orientation & 2) ? (m_itemsize.width() - local_style->m_background->size().width()) / 2 : 0;	 // vertical
			y += (orientation & 1) ? (m_itemsize.height() - local_style->m_background->size().height()) / 2 : 0; // horizontal
			painter.blit(local_style->m_background, ePoint(x, y), eRect(), gPainter::BT_ALPHATEST);
		}
		else if (local_style && local_style->is_set.background_gradient_color && !local_style->m_background && cursorValid)
			painter.drawGradient(itemrect, local_style->m_background_gradient_color_start, local_style->m_background_gradient_color_end, local_style->m_background_color_gradient_direction, local_style->m_background_color_gradient_flag);
		else if (selected && !local_style->m_selection)
			painter.clear();
	}

	// Draw frame here so to be drawn under icons
	if (selected && (!local_style || !local_style->m_selection) && (!local_style || !local_style->is_set.border))
		style.drawFrame(painter, eRect(offset, m_itemsize), eWindowStyle::frameListboxEntry);
	if (m_list && cursorValid)
	{
		/* get current list item */
		ePyObject item = PyList_GET_ITEM(m_list, cursorGet()); // borrowed reference!
		ePyObject text, value;
		painter.setFont(fnt);

		if (selected && local_style && local_style->m_selection)
		{
			int x = offset.x();
			int y = offset.y();
			x += (orientation & 2) ? (m_itemsize.width() - local_style->m_selection->size().width()) / 2 : 0;	// vertical
			y += (orientation & 1) ? (m_itemsize.height() - local_style->m_selection->size().height()) / 2 : 0; // horizontal
			painter.blit(local_style->m_selection, ePoint(x, y), eRect(), gPainter::BT_ALPHATEST);
		}
		else if (selected && local_style->is_set.background_gradient_selected_color && !local_style->m_selection)
			painter.drawGradient(itemrect, local_style->m_background_gradient_color_selected_start, local_style->m_background_gradient_color_selected_end, local_style->m_background_color_gradient_selected_direction, local_style->m_background_color_gradient_selected_flag);

		/* the first tuple element is a string for the left side.
		   the second one will be called, and the result shall be an tuple.

		   of this tuple,
		   the first one is the type (string).
		   the second one is the value. */
		if (PyTuple_Check(item))
		{
			/* handle left part. get item from tuple, convert to string, display. */
			text = PyTuple_GET_ITEM(item, 0);
			text = PyObject_Str(text); /* creates a new object - old object was borrowed! */
			const char *string = (text && PyString_Check(text)) ? PyString_AsString(text) : "<not-a-string>";
			eRect labelrect(ePoint(offset.x() + 15, offset.y()), m_itemsize);
			painter.renderText(labelrect, string,
							   gPainter::RT_HALIGN_LEFT | gPainter::RT_VALIGN_CENTER, border_color, border_size);
			Py_XDECREF(text);

			/* when we have no label, align value to the left. (FIXME:
			   don't we want to specifiy this individually?) */
			int value_alignment_left = !*string;

			/* now, handle the value. get 2nd part from tuple*/
			if (PyTuple_Size(item) >= 2) // when no 2nd entry is in tuple this is a non selectable entry without config part
				value = PyTuple_GET_ITEM(item, 1);

			if (value)
			{
				ePyObject args = PyTuple_New(1);
				PyTuple_SET_ITEM(args, 0, PyInt_FromLong(selected));

				/* CallObject will call __call__ which should return the value tuple */
				value = PyObject_CallObject(value, args);

				if (PyErr_Occurred())
					PyErr_Print();

				Py_DECREF(args);
				/* the PyInt was stolen. */
			}

			/*  check if this is really a tuple */
			if (value && PyTuple_Check(value))
			{
				/* convert type to string */
				ePyObject type = PyTuple_GET_ITEM(value, 0);
				const char *atype = (type && PyString_Check(type)) ? PyString_AsString(type) : 0;

				if (atype)
				{
					if (!strcmp(atype, "text") || !strcmp(atype, "mtext"))
					{
						ePyObject pvalue = PyTuple_GET_ITEM(value, 1);
						const char *text = (pvalue && PyString_Check(pvalue)) ? PyString_AsString(pvalue) : "<not-a-string>";
						painter.setFont(fnt2);
						int flags = value_alignment_left ? gPainter::RT_HALIGN_LEFT : gPainter::RT_HALIGN_RIGHT;
						int markedpos = -1;
						int cursor = cursorGet();
						if (m_text_offset.find(cursor) == m_text_offset.end())
							m_text_offset[cursor] = 0;

						if (!strcmp(atype, "mtext"))
						{
							if (PyTuple_Size(value) >= 3)
							{
								ePyObject plist = PyTuple_GET_ITEM(value, 2);
								int entries = 0;
								if (plist && PyList_Check(plist))
									entries = PyList_Size(plist);
								if (entries != 0)
								{
									ePyObject entry = PyList_GET_ITEM(plist, 0);
									if (PyInt_Check(entry))
									{
										markedpos = PyInt_AsLong(entry);
										// Assume sequential.
										if (entries > 1)
											markedpos |= entries << 16;
									}
								}
								/* entry is borrowed */
								/* plist is 0 or borrowed */
							}
						}
						/* find the width of the label, to prevent the value overwriting it. */
						ePoint valueoffset = offset;
						eSize valuesize = m_itemsize;
						int labelwidth = 0;
						if (*string)
						{
							ePtr<eTextPara> para = new eTextPara(labelrect);
							para->setFont(fnt);
							para->renderString(string, 0);
							labelwidth = para->getBoundBox().width() + 15;
						}
						valueoffset.setX(valueoffset.x() + 15 + labelwidth);
						valuesize.setWidth(valuesize.width() - 15 - labelwidth - 15);
						painter.renderText(eRect(valueoffset, valuesize), text, flags | gPainter::RT_VALIGN_CENTER, border_color, border_size, markedpos, &m_text_offset[cursor]);
						/* pvalue is borrowed */
					}
					else if (!strcmp(atype, "slider"))
					{

						ePyObject pvalue = PyTuple_GET_ITEM(value, 1);
						ePyObject pmin = PyTuple_GET_ITEM(value, 2);
						ePyObject pmax = PyTuple_GET_ITEM(value, 3);

						int value = (pvalue && PyInt_Check(pvalue)) ? PyInt_AsLong(pvalue) : 0;
						int min = (pmin && PyInt_Check(pmin)) ? PyInt_AsLong(pmin) : 0;
						int max = (pmax && PyInt_Check(pmax)) ? PyInt_AsLong(pmax) : 100;

						// if min < 0 and max < min -> replace min,max
						if (min < 0 && max < min)
						{
							int newmax = min;
							min = max;
							max = newmax;
						}

						// OLD					int size = (psize && PyInt_Check(psize)) ? PyInt_AsLong(psize) : 100;
						int value_area = 0;

						/* draw value at the end of the slider */
						if (eConfigManager::getConfigBoolValue("config.usage.show_slider_value", true))
						{
							value_area = 100;
							painter.setFont(fnt2);
							painter.renderText(eRect(ePoint(offset.x() - 15, offset.y()), m_itemsize), std::to_string(value), gPainter::RT_HALIGN_RIGHT | gPainter::RT_VALIGN_CENTER, border_color, border_size);
						}
						/* calc. slider length */
						int width = (m_itemsize.width() - m_seperation - 15 - value_area) * (value - min) / (max - min);
						// OLD					int width = (m_itemsize.width() - m_seperation - 15 - value_area) * value / size;
						int height = m_itemsize.height();

						/* draw slider */
						// painter.fill(eRect(offset.x() + m_seperation, offset.y(), width, height));
						if (m_slider_height % 2 != height % 2)
							m_slider_height -= 1;
						if (m_slider_height + 2 * m_slider_space >= height) // frame out of selector = without frame
							m_slider_space = 0;
						int slider_y_offset = (height - m_slider_height) / 2;
						if (m_slider_space)
						{
							ePoint tl(offset.x() + m_seperation, offset.y() + slider_y_offset - m_slider_space - 1);
							ePoint tr(offset.x() + m_itemsize.width() - 15 - value_area - 1, tl.y());
							ePoint bl(tl.x(), offset.y() + slider_y_offset + m_slider_height + m_slider_space);
							ePoint br(tr.x(), bl.y());
							painter.line(tl, tr);
							painter.line(tr, br);
							painter.line(br, bl);
							painter.line(bl, tl);
							painter.fill(eRect(offset.x() + m_seperation + m_slider_space + 1, offset.y() + slider_y_offset, width - 2 * (m_slider_space + 1), m_slider_height));
						}
						else
						{
							painter.fill(eRect(offset.x() + m_seperation, offset.y() + slider_y_offset, width, m_slider_height));
						}
						/* pvalue is borrowed */
					}
					else if (!strcmp(atype, "pixmap"))
					{
						ePyObject data;
						ePyObject ppixmap = PyTuple_GET_ITEM(value, 1);

						if (PyInt_Check(ppixmap) && data) /* if the pixemap is in fact a number, it refers to the 'data' list. */
							ppixmap = PyTuple_GetItem(data, PyInt_AsLong(ppixmap));

						ePtr<gPixmap> pixmap;
						if (SwigFromPython(pixmap, ppixmap))
						{
							eDebug("[eListboxPythonMultiContent] (Pixmap) get pixmap failed");
							const char *value = (ppixmap && PyString_Check(ppixmap)) ? PyString_AsString(ppixmap) : "<not-a-string>";
							painter.setFont(fnt2);
							if (value_alignment_left)
								painter.renderText(eRect(ePoint(offset.x() - 15, offset.y()), m_itemsize), value, gPainter::RT_HALIGN_LEFT | gPainter::RT_VALIGN_CENTER, border_color, border_size);
							else
								painter.renderText(eRect(ePoint(offset.x() - 15, offset.y()), m_itemsize), value, gPainter::RT_HALIGN_RIGHT | gPainter::RT_VALIGN_CENTER, border_color, border_size);
						}
						else
						{
							eRect rect(ePoint(m_itemsize.width() - pixmap->size().width() - 15, offset.y() + (m_itemsize.height() - pixmap->size().height()) / 2), pixmap->size());
							painter.clip(rect);
							painter.blit(pixmap, rect.topLeft(), rect, gPainter::BT_ALPHABLEND);
							painter.clippop();
						}
					}
				}
				/* type is borrowed */
			}
			else if (value)
				eWarning("[eListboxPythonConfigContent] second value of tuple is not a tuple.");
			if (value)
				Py_DECREF(value);
		}
	}

	painter.clippop();
}

int eListboxPythonConfigContent::currentCursorSelectable()
{
	return eListboxPythonStringContent::currentCursorSelectable();
}

//////////////////////////////////////

/* todo: make a real infrastructure here! */
RESULT SwigFromPython(ePtr<gPixmap> &res, PyObject *obj);

eListboxPythonMultiContent::eListboxPythonMultiContent()
	: m_clip(gRegion::invalidRegion()), m_old_clip(gRegion::invalidRegion())
{
}

eListboxPythonMultiContent::~eListboxPythonMultiContent()
{
	Py_XDECREF(m_buildFunc);
	Py_XDECREF(m_selectableFunc);
	Py_XDECREF(m_template);
}

void eListboxPythonMultiContent::setSelectionClip(eRect &rect, bool update)
{
	/* Please Note! This will currently only work for verticial list box */
	m_selection_clip = rect;
	if (m_listbox)
		rect.moveBy(ePoint(0, m_listbox->getEntryTop()));
	if (m_clip.valid())
		m_clip |= rect;
	else
		m_clip = rect;
	if (update && m_listbox)
		m_listbox->entryChanged(cursorGet());
}

static void clearRegionHelper(gPainter &painter, eListboxStyle *local_style, const ePoint &offset, const eSize &size, ePyObject &pbackColor, bool cursorValid, bool clear, int orientation)
{
	if (pbackColor)
	{
		unsigned int color = PyInt_AsUnsignedLongMask(pbackColor);
		painter.setBackgroundColor(gRGB(color));
	}
	else if (local_style)
	{
		if (local_style->is_set.background_color)
			painter.setBackgroundColor(local_style->m_background_color);
		if (local_style->is_set.background_gradient_color && cursorValid)
		{
			painter.drawGradient(eRect(offset, size), local_style->m_background_gradient_color_start, local_style->m_background_gradient_color_end, local_style->m_background_color_gradient_direction, local_style->m_background_color_gradient_flag);
			return;
		}
		if (local_style->m_background && cursorValid)
		{
			int x = offset.x();
			int y = offset.y();
			x += (orientation & 2) ? (size.width() - local_style->m_background->size().width()) / 2 : 0;   // vertical
			y += (orientation & 1) ? (size.height() - local_style->m_background->size().height()) / 2 : 0; // horizontal
			painter.blit(local_style->m_background, ePoint(x, y), eRect(), local_style->is_set.transparent_background ? gPainter::BT_ALPHATEST : 0);
			return;
		}
		else if (local_style->is_set.transparent_background)
			return;
	}
	if (clear)
		painter.clear();
}

static void clearRegionSelectedHelper(gPainter &painter, eListboxStyle *local_style, const ePoint &offset, const eSize &size, ePyObject &pbackColorSelected, bool cursorValid, bool clear, int orientation)
{
	if (pbackColorSelected)
	{
		unsigned int color = PyInt_AsUnsignedLongMask(pbackColorSelected);
		painter.setBackgroundColor(gRGB(color));
	}
	else if (local_style)
	{
		if (local_style->is_set.background_color_selected)
			painter.setBackgroundColor(local_style->m_background_color_selected);
		if (local_style->m_background && cursorValid)
		{
			int x = offset.x();
			int y = offset.y();
			x += (orientation & 2) ? (size.width() - local_style->m_background->size().width()) / 2 : 0;   // vertical
			y += (orientation & 1) ? (size.height() - local_style->m_background->size().height()) / 2 : 0; // horizontal
			painter.blit(local_style->m_background, ePoint(x, y), eRect(), local_style->is_set.transparent_background ? gPainter::BT_ALPHATEST : 0);
			return;
		}
		else if (local_style->is_set.background_gradient_selected_color && cursorValid)
		{
			painter.drawGradient(eRect(offset, size), local_style->m_background_gradient_color_selected_start, local_style->m_background_gradient_color_selected_end, local_style->m_background_color_gradient_selected_direction, local_style->m_background_color_gradient_selected_flag);
			return;
		}
	}
	if (clear)
		painter.clear();
}

static void clearRegion(gPainter &painter, eWindowStyle &style, eListboxStyle *local_style, ePyObject pforeColor, ePyObject pforeColorSelected, ePyObject pbackColor, ePyObject pbackColorSelected, int selected, gRegion &rc, eRect &sel_clip, const ePoint &offset, const eSize &size, bool cursorValid, bool clear, int orientation)
{
	if (selected && sel_clip.valid())
	{
		gRegion part = rc - sel_clip;
		if (!part.empty())
		{
			painter.clip(part);
			style.setStyle(painter, eWindowStyle::styleListboxNormal);
			clearRegionHelper(painter, local_style, offset, size, pbackColor, cursorValid, clear, orientation);
			painter.clippop();
			selected = 0;
		}
		part = rc & sel_clip;
		if (!part.empty())
		{
			painter.clip(part);
			style.setStyle(painter, eWindowStyle::styleListboxSelected);
			clearRegionSelectedHelper(painter, local_style, offset, size, pbackColorSelected, cursorValid, clear, orientation);
			painter.clippop();
			selected = 1;
		}
	}
	else if (selected)
	{
		style.setStyle(painter, eWindowStyle::styleListboxSelected);
		clearRegionSelectedHelper(painter, local_style, offset, size, pbackColorSelected, cursorValid, clear, orientation);
		if (local_style && local_style->m_selection)
		{
			int x = offset.x();
			int y = offset.y();
			x += (orientation & 2) ? (size.width() - local_style->m_selection->size().width()) / 2 : 0;	  // vertical
			y += (orientation & 1) ? (size.height() - local_style->m_selection->size().height()) / 2 : 0; // horizontal
			painter.blit(local_style->m_selection, ePoint(x, y), eRect(), gPainter::BT_ALPHATEST);
		}
	}
	else
	{
		style.setStyle(painter, eWindowStyle::styleListboxNormal);
		clearRegionHelper(painter, local_style, offset, size, pbackColor, cursorValid, clear, orientation);
	}

	if (selected)
	{
		if (pforeColorSelected)
		{
			unsigned int color = PyInt_AsUnsignedLongMask(pforeColorSelected);
			painter.setForegroundColor(gRGB(color));
		}
		/* if we have a local foreground color set, use that. */
		else if (local_style && local_style->is_set.foreground_color_selected)
			painter.setForegroundColor(local_style->m_foreground_color_selected);
	}
	else
	{
		if (pforeColor)
		{
			unsigned int color = PyInt_AsUnsignedLongMask(pforeColor);
			painter.setForegroundColor(gRGB(color));
		}
		/* if we have a local foreground color set, use that. */
		else if (local_style && local_style->is_set.foreground_color)
			painter.setForegroundColor(local_style->m_foreground_color);
	}
}

static ePyObject lookupColor(ePyObject color, ePyObject data)
{
	if (color == Py_None)
		return ePyObject();

	if ((!color) && (!data))
		return color;

	unsigned int icolor = PyInt_AsUnsignedLongMask(color);

	/* check if we have the "magic" template color */
	if (data && (icolor & 0xFF000000) == 0xFF000000)
	{
		int index = icolor & 0xFFFFFF;
		if (PyTuple_GetItem(data, index) == Py_None)
			return ePyObject();
		return PyTuple_GetItem(data, index);
	}

	if (color == Py_None)
		return ePyObject();

	return color;
}

void eListboxPythonMultiContent::paint(gPainter &painter, eWindowStyle &style, const ePoint &offset, int selected)
{

	eListboxStyle *local_style = 0;
	eRect sel_clip(m_selection_clip);
	bool cursorValid = this->cursorValid();
	gRGB border_color;
	int border_size = 0;
	int orientation = 0;
	bool itemZoomed = false;
	bool itemZoomContent = false;

	if (sel_clip.valid())
		sel_clip.moveBy(offset);

	/* get local listbox style, if present */
	if (m_listbox)
	{
		local_style = m_listbox->getLocalStyle();
		border_size = local_style->m_border_size;
		border_color = local_style->m_border_color;
		orientation = m_listbox->getOrientation();
		itemZoomed = local_style->m_selection_zoom > 1.0;
		itemZoomContent = itemZoomed && local_style->is_set.zoom_content;
	}

	ePoint offs = offset;
	ePoint zoomoffs = offset;
	eRect itemRect = eRect(offset, m_itemsize);
	gRegion itemregion(itemRect);

	if (selected && itemZoomed)
	{
		itemRect = eRect(offs, eSize(local_style->m_selection_width, local_style->m_selection_height));
		itemregion = itemRect;
		if (local_style->is_set.zoom_move_content)
		{
			zoomoffs = ePoint(offset.x() - (((local_style->m_selection_width) - m_itemsize.width()) / 4), offset.y() - (((local_style->m_selection_height) - m_itemsize.height()) / 4));
		}
	}
	else if (!selected && itemZoomed)
	{
		offs = ePoint(offset.x() + (((local_style->m_selection_width) - m_itemsize.width()) / 2), offset.y() + (((local_style->m_selection_height) - m_itemsize.height()) / 2));
		zoomoffs = offs;
		itemRect = eRect(offs, m_itemsize);
		itemregion = itemRect;
	}

	painter.clip(itemregion);
	clearRegion(painter, style, local_style, ePyObject(), ePyObject(), ePyObject(), ePyObject(), selected, itemregion, sel_clip, offs, itemRect.size(), cursorValid, true, orientation);
	// Draw frame here so to be under the content
	if (selected && !sel_clip.valid() && (!local_style || !local_style->m_selection) && (!local_style || !local_style->is_set.border))
		style.drawFrame(painter, eRect(offs, itemRect.size()), eWindowStyle::frameListboxEntry);

	ePyObject items, buildfunc_ret;

	if (m_list && cursorValid)
	{
		/* a multicontent list can be used in two ways:
			either each item is a list of (TYPE,...)-tuples,
			or there is a template defined, which is a list of (TYPE,...)-tuples,
			and the list is an unformatted tuple. The template then references items from the list.
		*/
		int cursor = cursorGet();
		items = PyList_GET_ITEM(m_list, cursor); // borrowed reference!

		if (m_buildFunc)
		{
			if (PyCallable_Check(m_buildFunc)) // when we have a buildFunc then call it
			{
				if (PyTuple_Check(items))
					buildfunc_ret = items = PyObject_CallObject(m_buildFunc, items);
				else
					eDebug("[eListboxPythonMultiContent] items is not a tuple");
			}
			else
				eDebug("[eListboxPythonMultiContent] buildfunc is not callable");
		}

		if (!items)
		{
			eDebug("[eListboxPythonMultiContent] error getting item %d", cursor);
			goto error_out;
		}

		if (!m_template)
		{
			if (!PyList_Check(items))
			{
				eDebug("[eListboxPythonMultiContent] list entry %d is not a list (non-templated)", cursor);
				goto error_out;
			}
		}
		else
		{
			if (!PyTuple_Check(items))
			{
				eDebug("[eListboxPythonMultiContent] list entry %d is not a tuple (templated)", cursor);
				goto error_out;
			}
		}

		ePyObject data;

		/* if we have a template, use the template for the actual formatting.
			we will later detect that "data" is present, and refer to that, instead
			of the immediate value. */
		int start = 1;
		if (m_template)
		{
			data = items;
			items = m_template;
			start = 0;
		}

		int items_size = PyList_Size(items);
		for (int i = start; i < items_size; ++i)
		{
			ePyObject item = PyList_GET_ITEM(items, i); // borrowed reference!

			if (!item)
			{
				eDebug("[eListboxPythonMultiContent] no items[%d] ?", i);
				goto error_out;
			}

			if (!PyTuple_Check(item))
			{
				eDebug("[eListboxPythonMultiContent] items[%d] is not a tuple.", i);
				goto error_out;
			}

			int size = PyTuple_Size(item);

			if (!size)
			{
				eDebug("[eListboxPythonMultiContent] items[%d] is an empty tuple.", i);
				goto error_out;
			}

			int type = PyInt_AsLong(PyTuple_GET_ITEM(item, 0));

			switch (type)
			{
			case TYPE_RECT:
			{
				ePyObject px = PyTuple_GET_ITEM(item, 1),
						  py = PyTuple_GET_ITEM(item, 2),
						  pwidth = PyTuple_GET_ITEM(item, 3),
						  pheight = PyTuple_GET_ITEM(item, 4),
						  pbackColor,
						  pbackColorSelected,
						  pforeColor,
						  pforeColorSelected, pborderWidth, pborderColor, pborderColorSelected;

				if (size > 5)
					pbackColor = lookupColor(PyTuple_GET_ITEM(item, 5), data);

				if (size > 6)
					pbackColorSelected = lookupColor(PyTuple_GET_ITEM(item, 6), data);

				if (size > 7)
				{
					pborderWidth = PyTuple_GET_ITEM(item, 7);
					if (pborderWidth == Py_None)
						pborderWidth = ePyObject();
				}

				if (size > 8)
				{
					pborderColor = lookupColor(PyTuple_GET_ITEM(item, 8), data);

					if (size > 9)
						pborderColorSelected = lookupColor(PyTuple_GET_ITEM(item, 9), data);
					else
						pborderColorSelected = pborderColor;
				}

				if (!(px && py && pwidth && pheight))
				{
					eDebug("[eListboxPythonMultiContent] tuple too small (must be (TYPE_RECT, x, y, width, height [, backgroundColor, backgroundColorSelected, borderWidth, borderColor, borderColorSelected])");
					goto error_out;
				}

				int x = PyFloat_Check(px) ? (int)PyFloat_AsDouble(px) : PyInt_AsLong(px);
				int y = PyFloat_Check(py) ? (int)PyFloat_AsDouble(py) : PyInt_AsLong(py);
				int width = PyFloat_Check(pwidth) ? (int)PyFloat_AsDouble(pwidth) : PyInt_AsLong(pwidth);
				int height = PyFloat_Check(pheight) ? (int)PyFloat_AsDouble(pheight) : PyInt_AsLong(pheight);
				int bwidth = pborderWidth ? PyInt_AsLong(pborderWidth) : 0;

				if (selected && itemZoomContent)
				{
					x = (x * local_style->m_selection_zoom) + offs.x();
					y = (y * local_style->m_selection_zoom) + offs.y();
					width *= local_style->m_selection_zoom;
					height *= local_style->m_selection_zoom;
				}
				else
				{
					x += zoomoffs.x();
					y += zoomoffs.y();
				}

				eRect rect(x + bwidth, y + bwidth, width - bwidth * 2, height - bwidth * 2);
				painter.clip(rect);
				{
					gRegion rc(rect);
					bool mustClear = (selected && pbackColorSelected) || (!selected && pbackColor);
					clearRegion(painter, style, local_style, pforeColor, pforeColorSelected, pbackColor, pbackColorSelected, selected, rc, sel_clip, offs, itemRect.size(), cursorValid, mustClear, orientation);
				}
				painter.clippop();

				if (bwidth)
				{
					eRect rect(eRect(x, y, width, height));
					painter.clip(rect);

					if (pborderColor)
					{
						unsigned int color = PyInt_AsUnsignedLongMask(selected ? pborderColorSelected : pborderColor);
						painter.setForegroundColor(gRGB(color));
					}

					rect.setRect(x, y, width, bwidth);
					painter.fill(rect);

					rect.setRect(x, y + bwidth, bwidth, height - bwidth);
					painter.fill(rect);

					rect.setRect(x + bwidth, y + height - bwidth, width - bwidth, bwidth);
					painter.fill(rect);

					rect.setRect(x + width - bwidth, y + bwidth, bwidth, height - bwidth);
					painter.fill(rect);

					painter.clippop();
				}

				break;
			}
			case TYPE_TEXT: // text
			{
				/*
					(0, x, y, width, height, fnt, flags, "bla" [, color, colorSelected, backColor, backColorSelected, borderWidth, borderColor] )
				*/
				ePyObject px = PyTuple_GET_ITEM(item, 1),
						  py = PyTuple_GET_ITEM(item, 2),
						  pwidth = PyTuple_GET_ITEM(item, 3),
						  pheight = PyTuple_GET_ITEM(item, 4),
						  pfnt = PyTuple_GET_ITEM(item, 5),
						  pflags = PyTuple_GET_ITEM(item, 6),
						  pstring = PyTuple_GET_ITEM(item, 7),
						  pforeColor, pforeColorSelected, pbackColor, pbackColorSelected, pborderWidth, pborderColor;

				if (!(px && py && pwidth && pheight && pfnt && pflags && pstring))
				{
					eDebug("[eListboxPythonMultiContent] tuple too small (must be (TYPE_TEXT, x, y, width, height, font, flags, string [, color, colorSelected, backColor, backColorSelected, borderWidth, borderColor])");
					goto error_out;
				}

				if (size > 8)
					pforeColor = lookupColor(PyTuple_GET_ITEM(item, 8), data);

				if (size > 9)
					pforeColorSelected = lookupColor(PyTuple_GET_ITEM(item, 9), data);

				if (size > 10)
					pbackColor = lookupColor(PyTuple_GET_ITEM(item, 10), data);

				if (size > 11)
					pbackColorSelected = lookupColor(PyTuple_GET_ITEM(item, 11), data);

				if (size > 12)
				{
					pborderWidth = PyTuple_GET_ITEM(item, 12);
					if (!pborderWidth || pborderWidth == Py_None)
						pborderWidth = ePyObject();
				}
				if (size > 13)
					pborderColor = lookupColor(PyTuple_GET_ITEM(item, 13), data);

				if (PyInt_Check(pstring) && data) /* if the string is in fact a number, it refers to the 'data' list. */
					pstring = PyTuple_GetItem(data, PyInt_AsLong(pstring));

				/* don't do anything if we have 'None' as string */
				if (!pstring || pstring == Py_None)
					continue;

				const char *string = (PyString_Check(pstring)) ? PyString_AsString(pstring) : "<not-a-string>";

				int x = PyFloat_Check(px) ? (int)PyFloat_AsDouble(px) : PyInt_AsLong(px);

				int y = PyFloat_Check(py) ? (int)PyFloat_AsDouble(py) : PyInt_AsLong(py);

				int width = PyFloat_Check(pwidth) ? (int)PyFloat_AsDouble(pwidth) : PyInt_AsLong(pwidth);
				int height = PyFloat_Check(pheight) ? (int)PyFloat_AsDouble(pheight) : PyInt_AsLong(pheight);

				int flags = PyInt_AsLong(pflags);
				int fnt = PyInt_AsLong(pfnt);
				int bwidth = pborderWidth ? PyInt_AsLong(pborderWidth) : 0;

				if (m_fonts.find(fnt) == m_fonts.end())
				{
					eDebug("[eListboxPythonMultiContent] specified font %d was not found!", fnt);
					goto error_out;
				}

				if (selected && itemZoomContent)
				{
					x = (x * local_style->m_selection_zoom) + offs.x();
					y = (y * local_style->m_selection_zoom) + offs.y();
					width *= local_style->m_selection_zoom;
					height *= local_style->m_selection_zoom;
				}
				else
				{
					x += zoomoffs.x();
					y += zoomoffs.y();
				}

				eRect rect(x + bwidth, y + bwidth, width - bwidth * 2, height - bwidth * 2);
				painter.clip(rect);

				{
					gRegion rc(rect);
					bool mustClear = (selected && pbackColorSelected) || (!selected && pbackColor);
					clearRegion(painter, style, local_style, pforeColor, pforeColorSelected, pbackColor, pbackColorSelected, selected, rc, sel_clip, offs, itemRect.size(), cursorValid, mustClear, orientation);
				}

				if (selected && itemZoomContent)
				{
					// find and set zoomed font
					if (m_fonts_zoomed.find(fnt) == m_fonts_zoomed.end())
						m_fonts_zoomed[fnt] = new gFont(m_fonts[fnt]->family, m_fonts[fnt]->pointSize * local_style->m_selection_zoom);
					painter.setFont(m_fonts_zoomed[fnt]);
				}
				else
					painter.setFont(m_fonts[fnt]);
				painter.renderText(rect, string, flags, border_color, border_size);
				painter.clippop();

				// draw border
				if (bwidth)
				{
					eRect rect(eRect(x, y, width, height));
					painter.clip(rect);
					if (pborderColor)
					{
						unsigned int color = PyInt_AsUnsignedLongMask(pborderColor);
						painter.setForegroundColor(gRGB(color));
					}

					rect.setRect(x, y, width, bwidth);
					painter.fill(rect);

					rect.setRect(x, y + bwidth, bwidth, height - bwidth);
					painter.fill(rect);

					rect.setRect(x + bwidth, y + height - bwidth, width - bwidth, bwidth);
					painter.fill(rect);

					rect.setRect(x + width - bwidth, y + bwidth, bwidth, height - bwidth);
					painter.fill(rect);

					painter.clippop();
				}
				break;
			}
			case TYPE_PROGRESS_PIXMAP: // Progress
			/*
				(1, x, y, width, height, filled_percent, pixmap [, borderWidth, foreColor, foreColorSelected, backColor, backColorSelected] )
			*/
			case TYPE_PROGRESS: // Progress
			{
				/*
					(1, x, y, width, height, filled_percent [, borderWidth, foreColor, foreColorSelected, backColor, backColorSelected] )
				*/
				ePyObject px = PyTuple_GET_ITEM(item, 1),
						  py = PyTuple_GET_ITEM(item, 2),
						  pwidth = PyTuple_GET_ITEM(item, 3),
						  pheight = PyTuple_GET_ITEM(item, 4),
						  pfilled_perc = PyTuple_GET_ITEM(item, 5),
						  ppixmap, pborderWidth, pforeColor, pforeColorSelected, pbackColor, pbackColorSelected;
				int idx = 6;
				if (type == TYPE_PROGRESS)
				{
					if (!(px && py && pwidth && pheight && pfilled_perc))
					{
						eDebug("[eListboxPythonMultiContent] tuple too small (must be (TYPE_PROGRESS, x, y, width, height, filled percent [, borderWidth, color, colorSelected, backColor, backColorSelected]))");
						goto error_out;
					}
				}
				else
				{
					ppixmap = PyTuple_GET_ITEM(item, idx++);
					if (!ppixmap || ppixmap == Py_None)
						continue;
					if (!(px && py && pwidth && pheight && pfilled_perc, ppixmap))
					{
						eDebug("[eListboxPythonMultiContent] tuple too small (must be (TYPE_PROGRESS_PIXMAP, x, y, width, height, filled percent, pixmap, [,borderWidth, color, colorSelected, backColor, backColorSelected]))");
						goto error_out;
					}
				}

				if (size > idx)
				{
					pborderWidth = PyTuple_GET_ITEM(item, idx++);
					if (!pborderWidth || pborderWidth == Py_None)
						pborderWidth = ePyObject();
				}
				if (size > idx)
				{
					pforeColor = PyTuple_GET_ITEM(item, idx++);
					if (!pforeColor || pforeColor == Py_None)
						pforeColor = ePyObject();
				}
				if (size > idx)
				{
					pforeColorSelected = PyTuple_GET_ITEM(item, idx++);
					if (!pforeColorSelected || pforeColorSelected == Py_None)
						pforeColorSelected = ePyObject();
				}
				if (size > idx)
				{
					pbackColor = PyTuple_GET_ITEM(item, idx++);
					if (!pbackColor || pbackColor == Py_None)
						pbackColor = ePyObject();
				}
				if (size > idx)
				{
					pbackColorSelected = PyTuple_GET_ITEM(item, idx++);
					if (!pbackColorSelected || pbackColorSelected == Py_None)
						pbackColorSelected = ePyObject();
				}

				int x = PyFloat_Check(px) ? (int)PyFloat_AsDouble(px) : PyInt_AsLong(px);

				int y = PyFloat_Check(py) ? (int)PyFloat_AsDouble(py) : PyInt_AsLong(py);

				int width = PyFloat_Check(pwidth) ? (int)PyFloat_AsDouble(pwidth) : PyInt_AsLong(pwidth);
				int height = PyFloat_Check(pheight) ? (int)PyFloat_AsDouble(pheight) : PyInt_AsLong(pheight);
				int filled = PyFloat_Check(pfilled_perc) ? (int)PyFloat_AsDouble(pfilled_perc) : PyInt_AsLong(pfilled_perc);

				if ((filled < 0) && data) /* if the string is in a negative number, it refers to the 'data' list. */
					filled = PyInt_AsLong(PyTuple_GetItem(data, -filled));

				/* don't do anything if percent out of range */
				if ((filled < 0) || (filled > 100))
					continue;

				int bwidth = pborderWidth ? PyInt_AsLong(pborderWidth) : 2;

				if (selected && itemZoomContent)
				{
					x = (x * local_style->m_selection_zoom) + offs.x();
					y = (y * local_style->m_selection_zoom) + offs.y();
					width *= local_style->m_selection_zoom;
					height *= local_style->m_selection_zoom;
				}
				else
				{
					x += zoomoffs.x();
					y += zoomoffs.y();
				}

				eRect rect(x, y, width, height);
				painter.clip(rect);

				{
					gRegion rc(rect);
					bool mustClear = (selected && pbackColorSelected) || (!selected && pbackColor);
					clearRegion(painter, style, local_style, pforeColor, pforeColorSelected, pbackColor, pbackColorSelected, selected, rc, sel_clip, offs, itemRect.size(), cursorValid, mustClear, orientation);
				}

				// border
				if (bwidth)
				{
					rect.setRect(x, y, width, bwidth);
					painter.fill(rect);

					rect.setRect(x, y + bwidth, bwidth, height - bwidth);
					painter.fill(rect);

					rect.setRect(x + bwidth, y + height - bwidth, width - bwidth, bwidth);
					painter.fill(rect);

					rect.setRect(x + width - bwidth, y + bwidth, bwidth, height - bwidth);
					painter.fill(rect);
				}

				rect.setRect(x + bwidth, y + bwidth, (width - bwidth * 2) * filled / 100, height - bwidth * 2);

				// progress
				if (ppixmap)
				{
					ePtr<gPixmap> pixmap;
					if (PyInt_Check(ppixmap) && data) /* if the pixmap is in fact a number, it refers to the data list */
						ppixmap = PyTuple_GetItem(data, PyInt_AsLong(ppixmap));

					if (SwigFromPython(pixmap, ppixmap))
					{
						eDebug("[eListboxPythonMultiContent] progressbar get pixmap failed");
						painter.clippop();
						continue;
					}
					if (pixmap->size().width() != width || pixmap->size().height() != height)
						painter.blitScale(pixmap, eRect(rect.left(), rect.top(), width, height), rect);
					else
						painter.blit(pixmap, rect.topLeft(), rect, 0);
				}
				else
					painter.fill(rect);

				painter.clippop();
				break;
			}
			case TYPE_LINEAR_GRADIENT_ALPHABLEND:
			case TYPE_LINEAR_GRADIENT:
			{
				ePyObject px = PyTuple_GET_ITEM(item, 1),
						  py = PyTuple_GET_ITEM(item, 2),
						  pwidth = PyTuple_GET_ITEM(item, 3),
						  pheight = PyTuple_GET_ITEM(item, 4),
						  ppdirection = PyTuple_GET_ITEM(item, 5),
						  pbackColor, pbackColorSelected, ppstartColor, pendColor, pstartColorSelected, pendColorSelected;

				if (!(px && py && pwidth && pheight && ppdirection))
				{
					eDebug("[eListboxPythonMultiContent] tuple too small (must be (TYPE_LINEAR_GRADIENT, x, y, width, height, direction, [, startColor, endColor, startColorSelected, endColorSelected] ))");
					goto error_out;
				}

				if (size > 6)
					ppstartColor = lookupColor(PyTuple_GET_ITEM(item, 6), data);

				if (size > 7)
					pendColor = lookupColor(PyTuple_GET_ITEM(item, 7), data);

				if (size > 8)
					pstartColorSelected = lookupColor(PyTuple_GET_ITEM(item, 8), data);

				if (size > 9)
					pendColorSelected = lookupColor(PyTuple_GET_ITEM(item, 9), data);

				int x = PyFloat_Check(px) ? (int)PyFloat_AsDouble(px) : PyInt_AsLong(px);
				int y = PyFloat_Check(py) ? (int)PyFloat_AsDouble(py) : PyInt_AsLong(py);
				int width = PyFloat_Check(pwidth) ? (int)PyFloat_AsDouble(pwidth) : PyInt_AsLong(pwidth);
				int height = PyFloat_Check(pheight) ? (int)PyFloat_AsDouble(pheight) : PyInt_AsLong(pheight);
				int direction = PyInt_AsLong(ppdirection);

				if (selected && itemZoomContent)
				{
					x = (x * local_style->m_selection_zoom) + offs.x();
					y = (y * local_style->m_selection_zoom) + offs.y();
					width *= local_style->m_selection_zoom;
					height *= local_style->m_selection_zoom;
				}
				else
				{
					x += zoomoffs.x();
					y += zoomoffs.y();
				}

				eRect rect(x, y, width, height);
				painter.clip(rect);
				{
					gRegion rc(rect);
					bool mustClear = (selected && pbackColorSelected) || (!selected && pbackColor);
					clearRegion(painter, style, local_style, ePyObject(), ePyObject(), pbackColor, pbackColorSelected, selected, rc, sel_clip, offs, itemRect.size(), cursorValid, mustClear, orientation);
				}

				int flag = type == TYPE_LINEAR_GRADIENT_ALPHABLEND ? gPainter::BT_ALPHABLEND : 0;

				if (!selected && ppstartColor && pendColor)
				{
					unsigned int color = PyInt_AsUnsignedLongMask(ppstartColor);
					unsigned int color1 = PyInt_AsUnsignedLongMask(pendColor);
					painter.drawGradient(rect, gRGB(color), gRGB(color1), direction, flag);
				}
				else if (selected && pstartColorSelected && pendColorSelected)
				{
					unsigned int color = PyInt_AsUnsignedLongMask(pstartColorSelected);
					unsigned int color1 = PyInt_AsUnsignedLongMask(pendColorSelected);
					painter.drawGradient(rect, gRGB(color), gRGB(color1), direction, flag);
				}

				painter.clippop();

				break;
			}
			case TYPE_PIXMAP_ALPHABLEND:
			case TYPE_PIXMAP_ALPHATEST:
			case TYPE_PIXMAP: // pixmap
			{
				/*
					(2, x, y, width, height, pixmap [, backColor, backColorSelected, flags] )
				*/

				ePyObject px = PyTuple_GET_ITEM(item, 1),
						  py = PyTuple_GET_ITEM(item, 2),
						  pwidth = PyTuple_GET_ITEM(item, 3),
						  pheight = PyTuple_GET_ITEM(item, 4),
						  ppixmap = PyTuple_GET_ITEM(item, 5),
						  pbackColor, pbackColorSelected;

				if (!(px && py && pwidth && pheight && ppixmap))
				{
					eDebug("[eListboxPythonMultiContent] tuple too small (must be (TYPE_PIXMAP, x, y, width, height, pixmap [, backColor, backColorSelected, flags] ))");
					goto error_out;
				}

				if (PyInt_Check(ppixmap) && data) /* if the pixmap is in fact a number, it refers to the 'data' list. */
					ppixmap = PyTuple_GetItem(data, PyInt_AsLong(ppixmap));

				/* don't do anything if we have 'None' as pixmap */
				if (!ppixmap || ppixmap == Py_None)
					continue;

				int x = PyFloat_Check(px) ? (int)PyFloat_AsDouble(px) : PyInt_AsLong(px);

				int y = PyFloat_Check(py) ? (int)PyFloat_AsDouble(py) : PyInt_AsLong(py);

				int width = PyFloat_Check(pwidth) ? (int)PyFloat_AsDouble(pwidth) : PyInt_AsLong(pwidth);
				int height = PyFloat_Check(pheight) ? (int)PyFloat_AsDouble(pheight) : PyInt_AsLong(pheight);

				int flags = 0;
				ePtr<gPixmap> pixmap;
				if (SwigFromPython(pixmap, ppixmap))
				{
					eDebug("[eListboxPythonMultiContent] (Pixmap) get pixmap failed");
					goto error_out;
				}

				if (size > 6)
					pbackColor = lookupColor(PyTuple_GET_ITEM(item, 6), data);

				if (size > 7)
					pbackColorSelected = lookupColor(PyTuple_GET_ITEM(item, 7), data);

				if (size > 8)
					flags = PyInt_AsLong(PyTuple_GET_ITEM(item, 8));

				if (selected && itemZoomContent)
				{
					x = (x * local_style->m_selection_zoom) + offs.x();
					y = (y * local_style->m_selection_zoom) + offs.y();
					width *= local_style->m_selection_zoom;
					height *= local_style->m_selection_zoom;
				}
				else
				{
					x += zoomoffs.x();
					y += zoomoffs.y();
				}

				eRect rect(x, y, width, height);
				painter.clip(rect);
				{
					gRegion rc(rect);
					bool mustClear = (selected && pbackColorSelected) || (!selected && pbackColor);
					clearRegion(painter, style, local_style, ePyObject(), ePyObject(), pbackColor, pbackColorSelected, selected, rc, sel_clip, offs, itemRect.size(), cursorValid, mustClear, orientation);
				}

				flags |= (type == TYPE_PIXMAP_ALPHATEST) ? gPainter::BT_ALPHATEST : (type == TYPE_PIXMAP_ALPHABLEND) ? gPainter::BT_ALPHABLEND
																													 : 0;
				painter.blit(pixmap, rect, rect, flags);
				painter.clippop();
				break;
			}
			default:
				eWarning("[eListboxPythonMultiContent] received unknown type (%d)", type);
				goto error_out;
			}
		}
	}

error_out:
	if (buildfunc_ret)
		Py_DECREF(buildfunc_ret);

	painter.clippop();
}

void eListboxPythonMultiContent::setBuildFunc(ePyObject cb)
{
	Py_XDECREF(m_buildFunc);
	m_buildFunc = cb;
	Py_XINCREF(m_buildFunc);
}

void eListboxPythonMultiContent::setSelectableFunc(ePyObject cb)
{
	Py_XDECREF(m_selectableFunc);
	m_selectableFunc = cb;
	Py_XINCREF(m_selectableFunc);
}

int eListboxPythonMultiContent::currentCursorSelectable()
{
	/* each list-entry is a list of tuples. if the first of these is none, it's not selectable */
	if (m_list && cursorValid())
	{
		if (m_selectableFunc && PyCallable_Check(m_selectableFunc))
		{
			ePyObject args = PyList_GET_ITEM(m_list, cursorGet()); // borrowed reference!
			if (PyTuple_Check(args))
			{
				ePyObject ret = PyObject_CallObject(m_selectableFunc, args);
				if (ret)
				{
					bool retval = ret == Py_True;
					Py_DECREF(ret);
					return retval;
				}
				eDebug("[eListboxPythonMultiContent] call m_selectableFunc failed!!! assume not callable");
			}
			else
				eDebug("[eListboxPythonMultiContent] m_list[m_cursor] is not a tuple!!! assume not callable");
		}
		else
		{
			ePyObject item = PyList_GET_ITEM(m_list, cursorGet());
			if (PyList_Check(item))
			{
				item = PyList_GET_ITEM(item, 0);
				if (item != Py_None)
					return 1;
			}
			else if (PyTuple_Check(item))
			{
				item = PyTuple_GET_ITEM(item, 0);
				if (item != Py_None)
					return 1;
			}
			else if (m_buildFunc && PyCallable_Check(m_buildFunc))
				return 1;
		}
	}
	return 0;
}

void eListboxPythonMultiContent::setFont(int fnt, gFont *font)
{
	if (font)
	{
		m_fonts[fnt] = font;
	}
	else
	{
		m_fonts.erase(fnt);
		m_fonts_zoomed.erase(fnt);
	}
}

void eListboxPythonMultiContent::setList(ePyObject list)
{
	m_old_clip = m_clip = gRegion::invalidRegion();
	eListboxPythonStringContent::setList(list);
}

void eListboxPythonMultiContent::resetClip()
{
	m_old_clip = m_clip = gRegion::invalidRegion();
}

void eListboxPythonMultiContent::updateClip(gRegion &clip)
{
	if (m_clip.valid())
	{
		clip &= m_clip;
		if (m_old_clip.valid() && !(m_clip - m_old_clip).empty())
			m_clip -= m_old_clip;
		m_old_clip = m_clip;
	}
	else
		m_old_clip = m_clip = gRegion::invalidRegion();
}

void eListboxPythonMultiContent::entryRemoved(int idx)
{
	if (m_listbox)
		m_listbox->entryRemoved(idx);
}

void eListboxPythonMultiContent::setTemplate(ePyObject tmplate)
{
	Py_XDECREF(m_template);
	m_template = tmplate;
	Py_XINCREF(m_template);
}
