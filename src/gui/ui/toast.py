"""
Toast notification widget for displaying floating messages to users.
"""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QPainter, QColor, QPainterPath
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect


class ToastNotification(QWidget):
    """Floating toast notification widget that auto-dismisses."""
    
    # Class variable to track all active toasts for stacking
    _active_toasts = []
    
    # Toast types with their colors and icons
    TYPES = {
        'error': {'bg': '#dc3545', 'icon': '⚠'},      # Warning triangle for error
        'warning': {'bg': '#fd7e14', 'icon': '⚡'},    # Lightning for warning
        'info': {'bg': '#0d6efd', 'icon': 'ℹ'},       # Info icon
        'success': {'bg': '#198754', 'icon': '✓'},    # Checkmark for success
    }
    
    def __init__(self, parent, message, toast_type='error', duration=5000):
        """
        Create a toast notification.
        
        Args:
            parent: Parent widget (main window)
            message: Message to display
            toast_type: One of 'error', 'warning', 'info', 'success'
            duration: Auto-dismiss duration in milliseconds (0 = no auto-dismiss)
        """
        super().__init__(parent)
        
        self.duration = duration
        self.toast_type = toast_type
        
        # Get type config
        type_config = self.TYPES.get(toast_type, self.TYPES['error'])
        self.bg_color = QColor(type_config['bg'])
        icon = type_config['icon']
        
        # Setup widget as overlay
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)  # Show clickable cursor
        
        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)
        
        # Icon label
        icon_label = QLabel(icon)
        icon_label.setFont(QFont('Arial', 18))
        icon_label.setStyleSheet('color: white; background: transparent;')
        layout.addWidget(icon_label)
        
        # Message label
        self.message_label = QLabel(message)
        self.message_label.setFont(QFont('Microsoft YaHei', 11))
        self.message_label.setStyleSheet('color: white; background: transparent;')
        self.message_label.setWordWrap(True)
        self.message_label.setMaximumWidth(400)
        layout.addWidget(self.message_label, 1)
        
        # Hint label (click to dismiss)
        hint_label = QLabel('点击关闭')
        hint_label.setFont(QFont('Microsoft YaHei', 9))
        hint_label.setStyleSheet('color: rgba(255, 255, 255, 0.7); background: transparent;')
        layout.addWidget(hint_label)
        
        # Opacity effect for fade animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)
        
        # Animations
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(200)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        self.fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(300)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InQuad)
        self.fade_out_animation.finished.connect(self._on_fade_out_finished)
        
        # Auto-dismiss timer
        if duration > 0:
            self.dismiss_timer = QTimer(self)
            self.dismiss_timer.setSingleShot(True)
            self.dismiss_timer.timeout.connect(self._start_fade_out)
        else:
            self.dismiss_timer = None
    
    def paintEvent(self, event):
        """Draw rounded rectangle background with shadow effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw shadow (slightly offset darker rectangle)
        shadow_path = QPainterPath()
        shadow_rect = QRect(2, 2, self.width() - 2, self.height() - 2).toRectF()
        shadow_path.addRoundedRect(shadow_rect, 10, 10)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 40))
        
        # Draw main rounded rectangle
        path = QPainterPath()
        path.addRoundedRect(QRect(0, 0, self.width() - 2, self.height() - 2).toRectF(), 10, 10)
        painter.fillPath(path, self.bg_color)
        
        super().paintEvent(event)
    
    def show_toast(self):
        """Show the toast with fade-in animation."""
        # Add to active toasts
        ToastNotification._active_toasts.append(self)
        
        # Adjust size first
        self.adjustSize()
        
        # Calculate position (center of parent window)
        self._update_position()
        
        # Show widget - raise it above other widgets
        self.show()
        self.raise_()
        
        # Start fade-in animation
        self.fade_in_animation.start()
        
        # Start auto-dismiss timer
        if self.dismiss_timer:
            self.dismiss_timer.start(self.duration)
    
    def _update_position(self):
        """Update position to center of parent window, stacked vertically."""
        if not self.parent():
            return
        
        parent_rect = self.parent().rect()
        
        # Calculate vertical offset based on other toasts (for stacking)
        y_offset = 0
        for toast in ToastNotification._active_toasts:
            if toast is self:
                break
            if toast.isVisible():
                y_offset += toast.height() + 10
        
        # Center horizontally
        x = (parent_rect.width() - self.width()) // 2
        
        # Position near top-center, with offset for stacking
        y = 60 + y_offset  # 60px from top
        
        self.move(x, y)
    
    def _start_fade_out(self):
        """Start the fade-out animation."""
        self.fade_out_animation.start()
    
    def _on_fade_out_finished(self):
        """Handle fade-out completion."""
        self.close()
    
    def close(self):
        """Close the toast and update other toasts' positions."""
        # Remove from active toasts
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
        
        # Update positions of remaining toasts
        for toast in ToastNotification._active_toasts:
            toast._update_position()
        
        super().close()
    
    def mousePressEvent(self, event):
        """Close toast on click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.close()


def show_toast(parent, message, toast_type='error', duration=5000):
    """
    Convenience function to show a toast notification.
    
    Args:
        parent: Parent widget (main window)
        message: Message to display
        toast_type: One of 'error', 'warning', 'info', 'success'
        duration: Auto-dismiss duration in milliseconds (0 = no auto-dismiss)
    
    Returns:
        ToastNotification: The created toast widget
    """
    toast = ToastNotification(parent, message, toast_type, duration)
    toast.show_toast()
    return toast
