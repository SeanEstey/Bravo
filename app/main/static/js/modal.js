
//------------------------------------------------------------------------------
function showModal(id, title, body, btn_prim_lbl, btn_sec_lbl) {

    $modal = $('#'+id);
    $modal.find('.modal-title').text(title);
    $modal.find('.modal-body').html(body);
    $modal.find('.btn-primary').text(btn_prim_lbl);
    $modal.find('.btn-secondary').text(btn_sec_lbl);
    $modal.find('.btn-primary').unbind('click'); // Clear prev btn handlers
    $modal.modal('show');
}

