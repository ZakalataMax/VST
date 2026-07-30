Dim objOutlook, objMail
On Error Resume Next
' Подключаемся к Outlook
Set objOutlook = GetObject(, "Outlook.Application")
If Err.Number <> 0 Then
    Set objOutlook = CreateObject("Outlook.Application")
End If
On Error GoTo 0
' Создаем письмо
Set objMail = objOutlook.CreateItem(0)
' Заполняем параметры (используем явное приведение к строке CStr)
objMail.To = CStr("m.zakalata@ornament-soft.com")
objMail.Subject = CStr("from Commanfline")
objMail.Body = CStr("Hi Test from Commanfline")
 
' --- ДОБАВЛЕНИЕ ВЛОЖЕНИЯ ---
' Укажите точный и полный путь к вашему файлу в кавычках
objMail.Attachments.Add "C:\Users\m.zakalata\source\repos\Parser\backend\dist\data\csv_reports_final\better-report-2026-06-12-to-2026-06-18.xlsx"
' ---------------------------
' Отправляем письмо
objMail.Send
' Очищаем память
Set objMail = Nothing
Set objOutlook = Nothing