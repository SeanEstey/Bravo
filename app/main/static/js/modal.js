
//------------------------------------------------------------------------------
function showModal(id, title, body, btn_prim_lbl, btn_sec_lbl) {

    $modal = $('#'+id);
    $modal.find('.modal-title').text(title);
    $modal.find('.modal-body').html(body);
    $modal.find('.modal-footer .btn-primary').text(btn_prim_lbl);
    $modal.find('.modal-footer .btn-secondary').text(btn_sec_lbl);
    $modal.find('.modal-footer .btn-primary').unbind('click'); // Clear prev btn handlers
    $modal.find('.modal-footer .btn-primary').off('click'); // Clear prev btn handlers
    $modal.modal('show');
}

