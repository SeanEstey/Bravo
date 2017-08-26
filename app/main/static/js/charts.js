/* charts.js */

MyMorris = null;
x_key='date';
y_keys=['value'];
top_lbl='$';
bDrawTopLabel = true;

//-------------------------------------------------------------------------------
function initCharts() {

    $(function() {
        MyMorris = window.MyMorris = {};
        MyMorris = Object.create(Morris);
        initLabelTopExt();
        console.log('morris.js initialized');
    });
}

//-------------------------------------------------------------------------------
function drawMorrisChart(id, data, xkey, ykeys,
    label_top=null, grid=null, axes=null, padding=null, hover_callback=null) {
    /*
    @data: list of {}'s with x_axis labels and y-values
    @labels: labels for the ykeys -- will be displayed when you hover over the chart
    @xkey, @ykeys: name of data record attribute containing x/y-values
    @element: id attr of selector graph drawn in 
    @lineColors: ['#5bc0de', '#5bc0de', '#5bc0de'],
    */

    var options = {
        element: id,
        data: data,
        xkey: xkey, 
        ykeys: ykeys,
        labels: ['$'], 
        axes: axes != null? axes : [],
        grid: grid? grid : false,
        hideHover: 'auto',
        barColors: ['#ec8380'],
        gridTextColor: ['#6a6c6f'],
        gridTextSize: 14,
        gridTextWeight: 300,
        padding: padding ? padding : 15,
        barSizeRatio: .80,
        barWidth: 25,
        resize: true
    };

    if(label_top != null)
        options['labelTop'] = label_top;

    if(hover_callback != null) {
        options['hoverCallback'] = hover_callback;
    }

    new Morris.Bar(options);

    $('svg').css('overflow','visible');
    //$('svg').css('top', '1px');
}

//-------------------------------------------------------------------------------
function initLabelTopExt() {
    /* Morris.js extension allowing for y-axis value on bar graphs to display
    */

    MyMorris.Bar.prototype.defaults["labelTop"] = false;

    // Label render
    MyMorris.Bar.prototype.drawLabelTop = function(xPos, yPos, text){
        var label;
        text = top_lbl + text;
        return label = this.raphael.text(xPos, yPos, text)
            .attr('font-size', this.options.gridTextSize)
            .attr('font-family', this.options.gridTextFamily)
            .attr('font-weight', this.options.gridTextWeight)
            .attr('fill', this.options.gridTextColor);
    };

    MyMorris.Bar.prototype.drawSeries = function() {

        var barWidth, bottom, groupWidth, idx, lastTop, left, leftPadding, numBars,
            row, sidx, size, spaceLeft, top, ypos, zeroPos;
        groupWidth = this.width / this.options.data.length;
        numBars = this.options.stacked ? 1 : this.options.ykeys.length;
        barWidth = (groupWidth * this.options.barSizeRatio - this.options.barGap * (numBars - 1)) / numBars;

        if (this.options.barSize) {
            barWidth = Math.min(barWidth, this.options.barSize);
        }

        // Create test top label. See if width too large to fit.
        var lblWidth = this.raphael.text(-10000,-10000,'$111').getBBox()['width'].toFixed(2);
        if(Number(lblWidth) > Number(barWidth).toFixed(2)){
            bDrawTopLabel = false;
            //console.log('Hiding top labels. labelWidth > barWidth');
        }
        else {
            //console.log('Showing top labels. labelWidth='+lblWidth+', barWidth='+barWidth.toFixed(2));
            //console.log('typeof(barWidth)='+typeof(barWidth)+', typeof(lblWidth)='+typeof(lblWidth));
        }

        spaceLeft = groupWidth - barWidth * numBars - this.options.barGap * (numBars - 1);
        leftPadding = spaceLeft / 2;
        zeroPos = this.ymin <= 0 && this.ymax >= 0 ? this.transY(0) : null;

        // Get bars func
        return this.bars = (function() {
            var _i, _len, _ref, _results;
            _ref = this.data;
            _results = [];

            for (idx = _i = 0, _len = _ref.length; _i < _len; idx = ++_i) {
                row = _ref[idx];
                lastTop = 0;

                // Push results func
                _results.push((function() {

                    var _j, _len1, _ref1, _results1;
                    _ref1 = row._y;
                    _results1 = [];

                    // Inner loop
                    for(sidx = _j = 0, _len1 = _ref1.length; _j < _len1; sidx = ++_j) {
                        ypos = _ref1[sidx];

                        if (ypos !== null) {
                            if (zeroPos) {
                                top = Math.min(ypos, zeroPos);
                                bottom = Math.max(ypos, zeroPos);
                            }
                            else {
                                top = ypos;
                                bottom = this.bottom;
                            }

                            left = this.left + idx * groupWidth + leftPadding;

                            if (!this.options.stacked) {
                                left += sidx * (barWidth + this.options.barGap);
                            }

                            size = bottom - top;

                            if(this.options.verticalGridCondition && this.options.verticalGridCondition(row.x)) {
                                this.drawBar(
                                    this.left + idx * groupWidth,
                                    this.top,
                                    groupWidth,
                                    Math.abs(this.top - this.bottom),
                                    this.options.verticalGridColor,
                                    this.options.verticalGridOpacity,
                                    this.options.barRadius,
                                    row.y[sidx]
                                );
                            }

                            if(this.options.stacked) {
                                top -= lastTop;
                            }

                            this.drawBar(
                                left,
                                top,
                                barWidth,
                                size,
                                this.colorFor(row, sidx, 'bar'),
                                this.options.barOpacity,
                                this.options.barRadius
                            );

                            _results1.push(lastTop += size);

                            if (this.options.labelTop == true && !this.options.stacked && bDrawTopLabel) {
                                console.log('labelTop=true');
                                label = this.drawLabelTop(
                                    (left + (barWidth / 2)),
                                    top - 10,
                                    row.y[sidx]
                                );

                                textBox = label.getBBox();
                                _results.push(textBox);
                            }
                        }
                        else {
                            _results1.push(null);
                        }
                    } // End inner loop

                    return _results1;

            }).call(this)); // End push results func
        }

        return _results;

        }).call(this); // end drawSeries
    };
}
