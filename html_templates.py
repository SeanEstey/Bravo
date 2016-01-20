
email_frame = '''
  <table style='max-width:600px; font-size:12pt;' border='1' cellspacing='0' cellpadding='0' align='center'>
    <tr>
      <td align='center' bgcolor='#ffffff' height='1'><img src='http://content.delivra.com/etapcontent//WinnifredStewartAssociation/Empties%20&amp;%20WINN%20Small.jpg' alt='' width='450' height='87' /></td>
    </tr>
    <tr>
      <td>
        <table cellpadding='25'>
          <tr>
            <td>
              <table style='font-size:12pt; width: 100%;' border='0' cellspacing='0' cellpadding='10' align='center'>
                !BODY!
                  <tr>
                    <td>
                      <hr/>
                    </td>
                  </tr>
                  <tr>
                    <td style='text-align:center;'>
                      <p><span style='font-size: 12pt;'>1-888-YOU-WINN</span></p>
                      <p><a title='emptiestowinn' href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a></p>
                    </td>
                  </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
'''



welcome_body = '''
<table style='max-width:600px; font-size:12pt;' border='1' cellspacing='0' cellpadding='0' align='center'>
  <tbody>
    <tr>
      <td align='center' bgcolor='#ffffff' height='1'><img src='http://content.delivra.com/etapcontent//WinnifredStewartAssociation/Empties%20&amp;%20WINN%20Small.jpg' alt='' width='450' height='87' /></td>
    </tr>
    <tr>
      <td>
        <table cellpadding='25'>
          <tr>
            <td>
              <table style='font-size:12pt; width: 100%;' border='0' cellspacing='0' cellpadding='10' align='center'>
                  <tr>
                    <td>
                      <p>Hi !FIRST_NAME!, </p>
                      <p>Thanks for signing up with Empties to Winn.</p>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      Dropoff Date: !DROPOFF_DATE!
                    </td>
                  </tr>
                  <tr>
                    <td>
                      Address: !ADDRESS!, !POSTAL!
                    </td>
                  </tr>
                  <tr>
                    <td style='font-size:12pt;'>
                      Please let us know if the address above is incorrect.
                      We'll leave you a Bag Buddy stand and green bags. You do not need to be home. 
                      If you have empties, you can label them <b>'WSA'</b> and place them at your front entrance by 8am.
                    </td>
                  </tr>
                  <tr>
                    <td style='font-size:12pt;'>
                      Residential pickups are scheduled every 10 weeks. 
                      We provide email/voice reminders and leave you a collection slip for your records.
                    </td>
                  </tr>
                  <tr>
                    <td style='font-size:12pt;'>
                      <p>We hope you enjoy the program.</span></p>
                      <p>&#160;</p>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <hr/>
                    </td>
                  </tr>
                  <tr>
                    <td style='text-align:center;'>
                      <p><span style='font-size: 12pt;'>1-888-YOU-WINN</span></p>
                      <p><a title='emptiestowinn' href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a></p>
                    </td>
                  </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </tbody>
</table>
'''

no_pickup_body = '''
  <html>
    <body style='font-size:12pt; text-align:left'>
      <div>
        <p>Thanks for letting us know you don't need a pickup. 
        This helps us to be more efficient with our resources.</p>
        
        <p>Your next pickup date will be on:</p>
        <p><h3>!DATE!</h3></p>
      </div>
      <div>
        1-888-YOU-WINN
        <br>
        <a href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a>
      </div>
    </body>
  </html>
'''
    
reminder_pickup_body = '''
  <html>
    <body style='font-size:12pt; text-align:left'>
      <div>
        <p>Hi, your upcoming Empties to WINN pickup date is</p>
        <p><h3>!DATE!</h3></p>
        <p>Your green bags can be placed at your front entrance, visible from the street, by 8am. 
        Please keep each bag under 30lbs.  
        Extra glass can be left in cases to the side.</p>
        <p><a style="!STYLE!" href='!HREF!'>Click here to cancel your pickup</a></p>
      </div>
      <div>
        1-888-YOU-WINN
        <br>
        <a href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a>
      </div>
    </body>
  </html>
'''

reminder_cancelling_body = '''
  <html>
    <body style='font-size:12pt; text-align:left;'>
      <p>Hi, this is a reminder that a driver will be by on !DATE! 
      to pickup your Empties to WINN collection stand.
      Thanks for your support.</p>
      <div>
        1-888-YOU-WINN
        <br>
        <a href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a>
      </div>
    </body>
  </html>
'''
